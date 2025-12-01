
# **Инженерный анализ архитектуры локального семантического поиска: SQLite, Векторные Встраивания и ORM**

## **Аннотация**

В современном ландшафте разработки программного обеспечения наблюдается выраженный сдвиг парадигмы в сторону архитектуры «Local-First» (локальность в приоритете), особенно в контексте персональных инструментов управления знаниями и небольших исследовательских проектов. Традиционно задачи семантического поиска решались посредством распределенных векторных баз данных (Pinecone, Milvus, Weaviate), требующих серверной инфраструктуры и сетевого взаимодействия. Однако для локальных задач, где приватность данных, отсутствие сетевых задержек и простота развертывания являются критическими факторами, такой подход избыточен и архитектурно неверен.  
Данное исследование представляет собой всеобъемлющий технический анализ построения системы гибридного поиска (сочетание семантического и лексического анализа) на базе встраиваемой СУБД SQLite. В центре внимания находится интеграция новейшего расширения sqlite-vec (написанного на чистом C) с передовыми возможностями Google Vertex AI Embeddings API v4. Особое внимание уделяется реализации слоя доступа к данным через Python ORM (SQLAlchemy 2.0 и Peewee) в условиях жесткого ограничения «без миграций», что характерно для прототипирования и личных инструментов.  
В работе детально рассматриваются механизмы асимметричного семантического поиска с использованием флагов task\_type, стратегии бинарного квантования для оптимизации памяти, а также алгоритмы слияния рангов (Reciprocal Rank Fusion) для реализации гибридной выдачи. Представленные архитектурные паттерны позволяют достичь суб-миллисекундной задержки поиска на наборах данных до миллиона векторов на стандартном потребительском оборудовании.  
---

## **1\. Эволюция и Архитектура Векторного Поиска в Экосистеме SQLite**

Внедрение векторных операций непосредственно в ядро реляционной базы данных трансформирует SQLite из простого хранилища строк в мощный движок для AI-приложений. В отличие от клиент-серверных решений, таких как PostgreSQL с расширением pgvector, архитектура SQLite подразумевает исполнение векторных вычислений в адресном пространстве процесса приложения, что исключает накладные расходы на сериализацию данных при передаче по сети.1

### **1.1. Сравнительный анализ: sqlite-vec против sqlite-vss**

Долгое время стандартом де\-факто для векторного поиска в SQLite являлось расширение sqlite-vss. Оно базировалось на библиотеке FAISS (Facebook AI Similarity Search), что обеспечивало доступ к продвинутым индексам, таким как Inverted File Index (IVF). Однако, зависимость от тяжеловесных C++ библиотек FAISS создавала существенные проблемы с переносимостью, особенно в среде Windows, и усложняла процесс сборки и распространения.3  
Появление sqlite-vec в 2024 году ознаменовало переход к нативной архитектуре. Написанное на чистом C, это расширение не имеет внешних зависимостей, что критически важно для концепции «run anywhere» (запуск везде), включая Raspberry Pi, WebAssembly в браузере и все десктопные ОС.1

| Характеристика | sqlite-vss (Legacy) | sqlite-vec (Modern) | Влияние на личные проекты |
| :---- | :---- | :---- | :---- |
| **Язык реализации** | C++ (обертка над FAISS) | Pure C | sqlite-vec проще в сборке и интеграции, нет проблем с DLL на Windows.7 |
| **Зависимости** | FAISS, OpenMP | Отсутствуют | Критично для портативных приложений (pip install работает надежно).8 |
| **Типы индексов** | IVF, Flat (через FAISS) | Brute-force (оптимизированный), Partitioning | Brute-force в sqlite-vec достаточно быстр для \<1M векторов благодаря SIMD.3 |
| **Хранение** | Shadow tables (ограничено) | Виртуальные таблицы vec0 | Улучшенное управление памятью, поддержка транзакций.6 |
| **Квантование** | Зависит от FAISS | Нативное бинарное (Int8/Bit) | Позволяет хранить миллионы векторов с минимальным потреблением RAM.10 |

Анализ показывает, что для стека «работа локально» sqlite-vec является безальтернативным выбором в 2025 году, обеспечивая лучшую производительность операций вставки (до 10 раз быстрее) и поиска (в 2-40 раз быстрее в зависимости от конфигурации) по сравнению с предшественниками.3

### **1.2. Механика Виртуальных Таблиц vec0**

sqlite-vec использует механизм виртуальных таблиц SQLite. При создании таблицы CREATE VIRTUAL TABLE items USING vec0(...), данные физически не хранятся в стандартном B-дереве SQLite в привычном виде. Вместо этого они организуются в «теневые таблицы» (shadow tables), оптимизированные для блочного чтения.6

#### **1.2.1. Управление памятью и производительность**

Ключевой особенностью sqlite-vec является то, что он не требует загрузки всего векторного индекса в оперативную память (RAM) для начала работы, в отличие от многих реализаций HNSW (Hierarchical Navigable Small World graphs). Векторы хранятся чанками (chunks), которые подгружаются постранично. Это позволяет работать с наборами данных, превышающими объем доступной RAM, полагаясь на страничный кэш операционной системы.6  
Однако для достижения максимальной производительности в локальных проектах рекомендуется использовать команду PRAGMA mmap\_size. Установка этого параметра в значение, близкое к размеру файла базы данных, позволяет отобразить файл в память (memory-mapped I/O), обеспечивая доступ к векторам со скоростью доступа к RAM без явного парсинга и десериализации.6

### **1.3. Бинарное Квантование и Rescoring**

Для локальных проектов ограничение по ресурсам (память и диск) часто является определяющим. sqlite-vec предоставляет встроенные функции для бинарного квантования (vec\_quantize\_binary), которое конвертирует 32-битные числа с плавающей точкой (float32) в 1-битные представления. Это уменьшает размер индекса в 32 раза.10  
Пример стратегии «Rescoring» (переоценка), реализуемой средствами SQL:

1. **Грубый поиск:** Выполняется поиск по дистанции Хэмминга на бинарных векторах. Это операция чрезвычайно быстрая, так как использует инструкции процессора POPCNT.  
2. **Точная переоценка:** Для топ-100 результатов, полученных на первом этапе, вычисляется точное косинусное расстояние или L2-дистанция с использованием исходных float32 векторов.

SQL

SELECT rowid, vec\_distance\_cosine(embedding, :query)  
FROM (  
  SELECT rowid, embedding  
  FROM items\_vec  
  WHERE embedding\_binary MATCH vec\_quantize\_binary(:query)  
  ORDER BY distance  
  LIMIT 100  
)  
ORDER BY 2  
LIMIT 10;

Данный подход, известный как *Matryoshka Representation Learning* в сочетании с квантованием, позволяет сохранять высокую точность (recall) при минимальных затратах ресурсов, что идеально подходит для стека локальных персональных проектов.7  
---

## **2\. Асимметричная Семантика: Google Vertex AI Embeddings API v4**

Выбор модели встраивания (embedding model) определяет интеллектуальный потенциал системы. Google Vertex AI API v4 (модель text-embedding-004) вводит концепцию **асимметричного семантического поиска** через параметр task\_type, что является критическим отличием от более старых моделей (например, word2vec или ранних версий BERT), где векторы запроса и документа обрабатывались идентично.13

### **2.1. Фундаментальное значение task\_type**

В традиционном векторном поиске часто возникает проблема: вектор вопроса «Как установить библиотеку?» может быть семантически далек от вектора ответа «Инструкция по установке пакетов через pip», если модель обучена только на семантической близость предложений (STS). Google решает это путем явного указания роли текста при генерации вектора.

* **RETRIEVAL\_QUERY**: Этот флаг **обязателен** для эмбеддинга запроса пользователя. Он трансформирует пространство векторов таким образом, чтобы вектор запроса «тянулся» к векторам, содержащим *ответы* на этот запрос, а не просто к похожим по формулировке предложениям.13  
* **RETRIEVAL\_DOCUMENT**: Этот флаг используется при индексации базы знаний (документов, заметок, статей). Он оптимизирует вектор для того, чтобы быть *найденным*.14

Игнорирование этих флагов или использование общего типа SEMANTIC\_SIMILARITY для задач поиска приведет к деградации качества выдачи (Recall Degradation), так как модель не будет учитывать вопросно-ответную структуру взаимодействия.14

### **2.2. Специализированные типы задач**

Для личных проектов разработчиков (например, локальный поиск по сниппетам кода) API предоставляет специализированный тип CODE\_RETRIEVAL\_QUERY.  
Этот тип задач обучен проецировать естественно-языковые запросы (например, «функция сортировки массива») в то же векторное пространство, где находятся блоки кода, эмбеддированные с типом RETRIEVAL\_DOCUMENT.13 Это позволяет реализовать функционал «умного поиска по коду», недоступный при использовании стандартных текстовых моделей.  
**Таблица совместимости типов задач:**

| Тип контента | Flag для индексации (База данных) | Flag для поиска (Запрос пользователя) |
| :---- | :---- | :---- |
| Текстовые документы | RETRIEVAL\_DOCUMENT | RETRIEVAL\_QUERY |
| Ответы на вопросы (Q\&A) | RETRIEVAL\_DOCUMENT (для ответов) | QUESTION\_ANSWERING |
| Программный код | RETRIEVAL\_DOCUMENT | CODE\_RETRIEVAL\_QUERY |
| Проверка фактов | RETRIEVAL\_DOCUMENT | FACT\_VERIFICATION |

Данные составлены на основе официальной документации Google Vertex AI.13

### **2.3. Интеграция Python SDK и Оптимизация**

При работе с text-embedding-004 через Python SDK важно учитывать параметр output\_dimensionality. Модель поддерживает усечение размерности (например, до 256 или 512 измерений) без существенной потери качества благодаря обучению по методологии Matryoshka.18  
Для локальных проектов использование меньшей размерности (например, 256 вместо 768\) линейно ускоряет поиск и уменьшает размер БД SQLite, что является разумным компромиссом. Однако важно помнить, что таблица vec0 в sqlite-vec строго типизирована по размерности (например, float), и изменение размерности потребует полной переиндексации (удаления и пересоздания таблицы).6  
---

## **3\. Слой Персистентности: ORM без Миграций**

Требование использования ORM (SQLAlchemy 2.0 или Peewee) без инструментов миграций (таких как Alembic) диктует специфический паттерн разработки, называемый «Schema-on-Startup» (схема при запуске) или «Idempotent Schema» (идемпотентная схема). В контексте личных проектов это означает, что приложение должно самостоятельно гарантировать корректность структуры БД при каждом запуске.

### **3.1. Выбор ORM: SQLAlchemy 2.0 против Peewee**

#### **3.1.1. Peewee: Легковесность и Гибкость**

Peewee исторически позиционируется как «маленькая и выразительная» ORM, что идеологически близко к философии SQLite. Для работы с нестандартными расширениями, такими как sqlite-vec, Peewee предоставляет более простой механизм расширения через VirtualModel и пользовательские поля.  
**Преимущества для задачи:**

* Простая декларация виртуальных таблиц.  
* Меньше «магии» метаклассов по сравнению с SQLAlchemy, что упрощает внедрение кастомного DDL (Data Definition Language).  
* Компактность кода инициализации.19

#### **3.1.2. SQLAlchemy 2.0: Строгость и Экосистема**

SQLAlchemy 2.0 представляет собой промышленный стандарт с полной поддержкой асинхронности и строгой типизацией. Однако, поддержка виртуальных таблиц SQLite (Virtual Tables) в ней не является нативной («из коробки»). Для реализации CREATE VIRTUAL TABLE требуется использование конструкций DDL и событий event.listen.21  
**Вердикт:** Для небольших личных проектов **Peewee** обеспечивает меньшее сопротивление среды при работе с расширениями SQLite. Однако, если проект планируется развивать в сторону сложной бизнес-логики, **SQLAlchemy 2.0** предпочтительнее, несмотря на вербозность настройки виртуальных таблиц.

### **3.2. Реализация Таблиц vec0 и Паттерны «Без Миграций»**

Поскольку sqlite-vec использует нестандартный SQL синтаксис (USING vec0), стандартные методы ORM (Base.metadata.create\_all()) могут не сработать корректно без дополнительных настроек.

#### **3.2.1. Паттерн инициализации в SQLAlchemy 2.0**

Для реализации подхода «без миграций» необходимо использовать сырой SQL для создания виртуальных таблиц, так как они не являются стандартными ANSI SQL таблицами.

Python

from sqlalchemy import create\_engine, text, event  
import sqlite\_vec

\# Функция подключения для загрузки расширения  
@event.listens\_for(engine, "connect")  
def load\_extensions(dbapi\_conn, conn\_record):  
    dbapi\_conn.enable\_load\_extension(True)  
    sqlite\_vec.load(dbapi\_conn) \# Загрузка sqlite-vec  
    dbapi\_conn.enable\_load\_extension(False)

def init\_db(engine):  
    with engine.connect() as conn:  
        \# Идемпотентное создание таблицы векторов  
        \# Обратите внимание на использование IF NOT EXISTS  
        conn.execute(text("""  
            CREATE VIRTUAL TABLE IF NOT EXISTS items\_vec USING vec0(  
                item\_id INTEGER PRIMARY KEY,  
                embedding float  
            );  
        """))  
        conn.commit()

Код иллюстрирует подход к инициализации виртуальной таблицы через SQLAlchemy с использованием сырого SQL, что обходит ограничения ORM на DDL виртуальных таблиц.21

#### **3.2.2. Стратегия управления изменениями схемы**

В отсутствие миграций, любое изменение параметров эмбеддингов (например, смена модели с 768 на 512 измерений) требует полной перестройки таблицы. Алгоритм действий приложения при старте:

1. Проверить существование таблицы.  
2. Если существует, проверить метаданные (например, версию модели эмбеддингов, сохраненную в отдельной таблице metadata).  
3. Если версии не совпадают: DROP TABLE items\_vec \-\> CREATE VIRTUAL TABLE... \-\> Запуск процесса переиндексации (re-indexing).

Этот подход («Destroy and Rebuild») допустим и даже рекомендован для локальных векторных индексов, так как они являются *производными данными* от основного контента.11

### **3.3. Связывание данных и Векторов**

Критически важно синхронизировать rowid виртуальной таблицы vec0 с primary key основной таблицы контента.  
При вставке данных следует явно указывать rowid:

SQL

INSERT INTO items\_vec(rowid, embedding)  
VALUES (:id\_from\_main\_table, :vector\_blob);

Это позволяет выполнять эффективные JOIN-запросы между метаданными (SQLAlchemy модель) и векторами (virtual table) без необходимости хранить избыточные данные.2  
---

## **4\. Гибридный Поиск: Архитектурный Синтез**

Гибридный поиск объединяет точность лексического поиска (по ключевым словам) с широтой охвата семантического поиска. В экосистеме SQLite это реализуется через комбинацию расширения **FTS5** (Full-Text Search 5\) и **sqlite-vec**.

### **4.1. FTS5: Лексический слой**

SQLite имеет мощный встроенный движок полнотекстового поиска FTS5. Он поддерживает морфологию (через стеммеры), булевы операторы (AND, OR, NOT), поиск фраз и префиксов. Для гибридного поиска FTS5 отвечает за нахождение точных совпадений, которые векторные модели могут пропустить (например, специфические аббревиатуры, артикулы или редкие имена собственные).23

### **4.2. Стратегии Фильтрации и Слияния**

#### **4.2.1. Pre-filtering (Предварительная фильтрация)**

sqlite-vec версии 0.1.6+ ввел поддержку **Partition Keys** (ключей партицирования) и **Metadata Columns**. Это позволяет выполнять фильтрацию *до* выполнения дорогостоящего сканирования векторов.

* **Partition Key:** Если в таблице vec0 колонка объявлена как partition key (например, user\_id или category\_id), индекс физически разделяется на шарды. Запрос с условием WHERE category\_id \=? будет сканировать только соответствующий шард. Это обеспечивает O(1) масштабируемость по количеству категорий.24  
* **Metadata Columns:** Позволяют хранить скалярные данные (год, тег) внутри векторного индекса для использования в WHERE.2

#### **4.2.2. Reciprocal Rank Fusion (RRF)**

Простое сложение скоров (BM25 от FTS5 и Cosine Similarity от sqlite-vec) математически некорректно, так как они имеют разное распределение и масштаб. Алгоритм RRF решает эту проблему, ранжируя документы исключительно по их позиции в списках выдачи.  
Формула RRF:

$$score(d) \= \\sum\_{r \\in R} \\frac{1}{k \+ r(d)}$$

где $r(d)$ — ранг документа в конкретной выдаче, а $k$ — константа (обычно 60).  
Реализация RRF в SQLite требует использования Common Table Expressions (CTE) для получения двух независимых списков и их последующего объединения.26

### **4.3. Пример SQL-запроса для Гибридного Поиска**

Ниже представлен оптимизированный запрос, реализующий гибридный поиск с RRF, использующий параметры SQLAlchemy (:query\_vec, :query\_text, :k):

SQL

WITH
  \-- 1\. Семантический поиск (Vector Search)  
  vec\_matches AS (  
    SELECT
      rowid,
      distance,  
      ROW\_NUMBER() OVER (ORDER BY distance) as rank\_vec  
    FROM items\_vec  
    WHERE embedding MATCH :query\_vec  
      AND k \= :limit\_vec  \-- Количество кандидатов от векторного поиска  
  ),  

  \-- 2\. Лексический поиск (Keyword Search)  
  fts\_matches AS (  
    SELECT
      rowid,
      rank,  
      ROW\_NUMBER() OVER (ORDER BY rank) as rank\_fts  
    FROM items\_fts  
    WHERE items\_fts MATCH :query\_text  
    LIMIT :limit\_fts \-- Количество кандидатов от FTS  
  )

\-- 3\. Слияние и RRF (Reciprocal Rank Fusion)  
SELECT
  COALESCE(vec.rowid, fts.rowid) as id,  
  (  
    COALESCE(1.0 / (60 \+ vec.rank\_vec), 0.0) \+
    COALESCE(1.0 / (60 \+ fts.rank\_fts), 0.0)  
  ) as rrf\_score  
FROM vec\_matches vec  
FULL OUTER JOIN fts\_matches fts ON vec.rowid \= fts.rowid  
ORDER BY rrf\_score DESC  
LIMIT :final\_limit;

*Примечание: SQLite поддерживает FULL OUTER JOIN начиная с новых версий, либо его можно эмулировать через UNION ALL. Для простоты в личных проектах часто достаточно LEFT JOIN или объединения списков на стороне Python.*  
---

## **5\. Практическое Руководство по Реализации**

В данном разделе описывается пошаговый процесс интеграции компонентов.

### **5.1. Установка и Окружение**

Для работы требуется Python 3.9+ и установка следующих пакетов:

Bash

pip install sqlite-vec google-cloud-aiplatform sqlalchemy

Важно: sqlite-vec поставляется в виде готовых колес (wheels) для Windows, macOS и Linux, что решает проблемы компиляции, характерные для sqlite-vss.8

### **5.2. Клиент Google Vertex AI**

Инициализация клиента для получения эмбеддингов требует правильной настройки task\_type.

Python

from vertexai.language\_models import TextEmbeddingInput, TextEmbeddingModel

def embed\_documents(texts: list\[str\]) \-\> list\[list\[float\]\]:  
    """Генерация эмбеддингов для сохранения в БД (Task: RETRIEVAL\_DOCUMENT)"""  
    model \= TextEmbeddingModel.from\_pretrained("text-embedding-004")  
    inputs \=  
    \# Получение векторов (batching рекомендуется для больших объемов)  
    embeddings \= model.get\_embeddings(inputs)  
    return \[e.values for e in embeddings\]

def embed\_query(text: str) \-\> list\[float\]:  
    """Генерация эмбеддинга для поискового запроса (Task: RETRIEVAL\_QUERY)"""  
    model \= TextEmbeddingModel.from\_pretrained("text-embedding-004")  
    inputs \=  
    embeddings \= model.get\_embeddings(inputs)  
    return embeddings.values

Этот код демонстрирует применение асимметричного поиска: документы кодируются иначе, чем запросы, что повышает релевантность.13

### **5.3. Инициализация Базы Данных (Peewee Пример)**

Пример использования Peewee для создания схемы с vec0 и fts5 без миграций.

Python

from peewee import \*  
from playhouse.sqlite\_ext import SqliteExtDatabase

db \= SqliteExtDatabase('local\_knowledge.db')

\# Загрузка расширения при подключении  
def load\_vec\_extension(conn):  
    conn.enable\_load\_extension(True)  
    \# Имя расширения может отличаться в зависимости от ОС, часто 'vec0' достаточно  
    \# если установлено через pip, часто требуется явная загрузка через sqlite\_vec.load(conn)  
    import sqlite\_vec  
    sqlite\_vec.load(conn)
    conn.enable\_load\_extension(False)

\# Модель данных  
class Document(Model):  
    content \= TextField()  
    metadata \= JSONField() \# Для доп. данных  

    class Meta:  
        database \= db

\# Инициализация  
db.connect()  
load\_vec\_extension(db.connection())

\# Создание таблиц (Raw SQL для vec0)  
db.execute\_sql("""  
    CREATE VIRTUAL TABLE IF NOT EXISTS document\_vec USING vec0(  
        rowid INTEGER PRIMARY KEY,  
        embedding float  
    )  
""")

db.execute\_sql("""  
    CREATE VIRTUAL TABLE IF NOT EXISTS document\_fts USING fts5(  
        content,  
        content\_rowid='rowid'  
    )  
""")

Использование execute\_sql для виртуальных таблиц является наиболее надежным методом в условиях ограничений ORM.2  
---

## **6\. Производительность и Ограничения**

### **6.1. Масштабируемость Локального Решения**

Тесты показывают, что sqlite-vec способен обрабатывать до 1 миллиона векторов (768-dim) с приемлемой задержкой (\<50-100 мс) на современном ноутбуке при использовании квантования. Без квантования, размер индекса для 1M векторов составит около 3 ГБ, что может быть существенно для оперативной памяти.10

### **6.2. Влияние «Холодного Старта»**

Поскольку SQLite — это файл, при первом запросе данные должны быть прочитаны с диска. sqlite-vec оптимизирован для последовательного чтения чанков, но первый запрос может быть медленнее («разогрев кэша»). Использование SSD накопителей является обязательным требованием для хорошей производительности векторного поиска в SQLite.

### **6.3. Отсутствие Индексов HNSW**

На данный момент sqlite-vec реализует только оптимизированный полный перебор (brute-force) и партицирование. В нем нет графовых индексов (HNSW), которые есть в pgvector или chroma. Это означает, что сложность поиска линейна O(N) (или O(N/K) при партицировании). Для «небольших личных проектов» (до 100k-500k записей) это преимущество, а не недостаток: полное сканирование дает 100% точность (Recall) и не требует длительного времени построения индекса.9  
---

## **7\. Заключение**

Создание локальной системы семантического поиска на стеке SQLite \+ Google Embeddings v4 \+ Python ORM — это не просто жизнеспособная, но и высокоэффективная архитектура для персональных проектов в 2025 году.  
Отказ от тяжеловесных векторных баз данных в пользу встраиваемого sqlite-vec существенно упрощает архитектуру (нет Docker-контейнеров, нет сетевых вызовов к БД). Использование флагов task\_type в Google API обеспечивает качество поиска уровня State-of-the-Art. Применение гибридного подхода с RRF компенсирует недостатки как чисто векторного, так и чисто лексического поиска.  
Для разработчика это означает возможность создать инструмент уровня Obsidian или Notion с AI-поиском, который работает полностью локально (за исключением вызова API эмбеддингов при индексации), хранит все данные в одном .db файле и не требует сложной поддержки инфраструктуры.

#### **Источники**

1. asg017/sqlite-vec: A vector search SQLite extension that runs anywhere\! \- GitHub, дата последнего обращения: декабря 1, 2025, [https://github.com/asg017/sqlite-vec](https://github.com/asg017/sqlite-vec)  
2. How sqlite-vec Works for Storing and Querying Vector Embeddings | by Stephen Collins, дата последнего обращения: декабря 1, 2025, [https://medium.com/@stephenc211/how-sqlite-vec-works-for-storing-and-querying-vector-embeddings-165adeeeceea](https://medium.com/@stephenc211/how-sqlite-vec-works-for-storing-and-querying-vector-embeddings-165adeeeceea)  
3. Vectorlite: a fast vector search extension for SQLite : r/Python \- Reddit, дата последнего обращения: декабря 1, 2025, [https://www.reddit.com/r/Python/comments/1e26xsm/vectorlite\_a\_fast\_vector\_search\_extension\_for/](https://www.reddit.com/r/Python/comments/1e26xsm/vectorlite_a_fast_vector_search_extension_for/)  
4. asg017/sqlite-vss: A SQLite extension for efficient vector search, based on Faiss\! \- GitHub, дата последнего обращения: декабря 1, 2025, [https://github.com/asg017/sqlite-vss](https://github.com/asg017/sqlite-vss)  
5. Pre-compiled loadable extension won't load on Python (3.10.8, Win11) · Issue \#13 · asg017/sqlite-vec \- GitHub, дата последнего обращения: декабря 1, 2025, [https://github.com/asg017/sqlite-vec/issues/13](https://github.com/asg017/sqlite-vec/issues/13)  
6. I'm writing a new vector search SQLite Extension | Alex Garcia's Blog, дата последнего обращения: декабря 1, 2025, [https://alexgarcia.xyz/blog/2024/building-new-vector-search-sqlite/index.html](https://alexgarcia.xyz/blog/2024/building-new-vector-search-sqlite/index.html)  
7. I'm writing a new vector search SQLite Extension \- Hacker News, дата последнего обращения: декабря 1, 2025, [https://news.ycombinator.com/item?id=40243168](https://news.ycombinator.com/item?id=40243168)  
8. sqlite-vec \- PyPI, дата последнего обращения: декабря 1, 2025, [https://pypi.org/project/sqlite-vec/](https://pypi.org/project/sqlite-vec/)  
9. Introducing sqlite-vec v0.1.0: a vector search SQLite extension that runs everywhere \- Reddit, дата последнего обращения: декабря 1, 2025, [https://www.reddit.com/r/LocalLLaMA/comments/1ehlazq/introducing\_sqlitevec\_v010\_a\_vector\_search\_sqlite/](https://www.reddit.com/r/LocalLLaMA/comments/1ehlazq/introducing_sqlitevec_v010_a_vector_search_sqlite/)  
10. Binary Quantization | sqlite-vec \- Alex Garcia, дата последнего обращения: декабря 1, 2025, [https://alexgarcia.xyz/sqlite-vec/guides/binary-quant.html](https://alexgarcia.xyz/sqlite-vec/guides/binary-quant.html)  
11. Introducing sqlite-vec v0.1.0: a vector search SQLite extension that runs everywhere | Alex Garcia's Blog, дата последнего обращения: декабря 1, 2025, [https://alexgarcia.xyz/blog/2024/sqlite-vec-stable-release/index.html](https://alexgarcia.xyz/blog/2024/sqlite-vec-stable-release/index.html)  
12. How to decide between SQLite database vs. in-memory usage \- Stack Overflow, дата последнего обращения: декабря 1, 2025, [https://stackoverflow.com/questions/7067798/how-to-decide-between-sqlite-database-vs-in-memory-usage](https://stackoverflow.com/questions/7067798/how-to-decide-between-sqlite-database-vs-in-memory-usage)  
13. Choose an embeddings task type | Generative AI on Vertex AI | Google Cloud Documentation, дата последнего обращения: декабря 1, 2025, [https://docs.cloud.google.com/vertex-ai/generative-ai/docs/embeddings/task-types](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/embeddings/task-types)  
14. Improve Gen AI Search with Vertex AI Embeddings and Task Types | Google Cloud Blog, дата последнего обращения: декабря 1, 2025, [https://cloud.google.com/blog/products/ai-machine-learning/improve-gen-ai-search-with-vertex-ai-embeddings-and-task-types](https://cloud.google.com/blog/products/ai-machine-learning/improve-gen-ai-search-with-vertex-ai-embeddings-and-task-types)  
15. Text embeddings API | Generative AI on Vertex AI \- Google Cloud Documentation, дата последнего обращения: декабря 1, 2025, [https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/text-embeddings-api](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/text-embeddings-api)  
16. Embeddings | Gemini API \- Google AI for Developers, дата последнего обращения: декабря 1, 2025, [https://ai.google.dev/gemini-api/docs/embeddings](https://ai.google.dev/gemini-api/docs/embeddings)  
17. Embeddings for Text – Vertex AI \- Google Cloud Console, дата последнего обращения: декабря 1, 2025, [https://console.cloud.google.com/vertex-ai/publishers/google/model-garden/textembedding-gecko](https://console.cloud.google.com/vertex-ai/publishers/google/model-garden/textembedding-gecko)  
18. Get text embeddings | Generative AI on Vertex AI \- Google Cloud Documentation, дата последнего обращения: декабря 1, 2025, [https://docs.cloud.google.com/vertex-ai/generative-ai/docs/embeddings/get-text-embeddings](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/embeddings/get-text-embeddings)  
19. peewee — peewee 3.18.3 documentation, дата последнего обращения: декабря 1, 2025, [http://docs.peewee-orm.com/](http://docs.peewee-orm.com/)  
20. Example app — peewee 3.18.3 documentation, дата последнего обращения: декабря 1, 2025, [https://docs.peewee-orm.com/en/latest/peewee/example.html](https://docs.peewee-orm.com/en/latest/peewee/example.html)  
21. SQLite — SQLAlchemy 2.0 Documentation, дата последнего обращения: декабря 1, 2025, [http://docs.sqlalchemy.org/en/latest/dialects/sqlite.html](http://docs.sqlalchemy.org/en/latest/dialects/sqlite.html)  
22. Create sqlite virtual table in Python \- Stack Overflow, дата последнего обращения: декабря 1, 2025, [https://stackoverflow.com/questions/7606797/create-sqlite-virtual-table-in-python](https://stackoverflow.com/questions/7606797/create-sqlite-virtual-table-in-python)  
23. Hybrid full-text search and vector search with SQLite | Alex Garcia's Blog, дата последнего обращения: декабря 1, 2025, [https://alexgarcia.xyz/blog/2024/sqlite-vec-hybrid-search/index.html](https://alexgarcia.xyz/blog/2024/sqlite-vec-hybrid-search/index.html)  
24. Partition keys support · Issue \#29 · asg017/sqlite-vec \- GitHub, дата последнего обращения: декабря 1, 2025, [https://github.com/asg017/sqlite-vec/issues/29](https://github.com/asg017/sqlite-vec/issues/29)  
25. sqlite-vec Update Introduces Metadata Columns, Partitioning, and Auxiliary Features for Enhanced Data Retrieval: Transforming Vector Search \- MarkTechPost, дата последнего обращения: декабря 1, 2025, [https://www.marktechpost.com/2024/11/25/sqlite-vec-update-introduces-metadata-columns-partitioning-and-auxiliary-features-for-enhanced-data-retrieval-transforming-vector-search/](https://www.marktechpost.com/2024/11/25/sqlite-vec-update-introduces-metadata-columns-partitioning-and-auxiliary-features-for-enhanced-data-retrieval-transforming-vector-search/)  
26. montraydavis/SemanticKernel\_SqliteVec\_Example: In-depth demonstration of C\# Semantic Kernel SQLiteVec Hybrid Search Tutorial \- Audio Guide \- GitHub, дата последнего обращения: декабря 1, 2025, [https://github.com/montraydavis/SemanticKernel\_SqliteVec\_Example](https://github.com/montraydavis/SemanticKernel_SqliteVec_Example)  
27. Simon Willison on vector-search, дата последнего обращения: декабря 1, 2025, [https://simonwillison.net/tags/vector-search/](https://simonwillison.net/tags/vector-search/)
