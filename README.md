# 🩺 Top Doctors Finder

Top Doctors Finder is a **Streamlit-based medical research discovery
application** that searches PubMed for a medical or research topic and
ranks the authors of the most relevant research papers.

The application combines:

-   **Streamlit** for the web interface
-   **NCBI PubMed E-utilities API** for medical research data
-   **MySQL** for user accounts and search/article storage
-   **bcrypt** for password hashing
-   **Sentence Transformers** for semantic embeddings
-   **Cosine similarity** for relevance scoring
-   An **author-position weighting system** to rank first, last, and
    middle authors differently

> **Important:** The application ranks **PubMed paper authors**. It does
> not verify that a person is a licensed medical doctor or that they
> currently practice medicine. The term "doctor" in the UI is therefore
> best understood as "research author/expert associated with relevant
> publications."

------------------------------------------------------------------------

## 1. What problem does this project solve?

Suppose a user wants to find researchers associated with a medical topic
such as:

-   breast cancer
-   diabetes
-   immunotherapy
-   lung cancer
-   cardiovascular disease
-   machine learning in healthcare

Instead of manually opening many PubMed papers and checking their
authors, the application automates the process.

The user enters a topic, and the application:

1.  Searches PubMed.
2.  Retrieves matching article IDs.
3.  Downloads article information.
4.  Extracts titles, authors, journals, publication dates, and
    abstracts.
5.  Stores the search results in MySQL.
6.  Converts the user's query and article abstracts into semantic
    embeddings.
7.  Calculates semantic similarity between the query and each article.
8.  Gives more weight to first and last authors than middle authors.
9.  Produces a ranked list of up to 10 authors.
10. Displays the author, author role, relevance score, and the paper
    that produced the author's best score.

------------------------------------------------------------------------

# 2. High-level architecture

``` text
                    ┌──────────────────────┐
                    │      User            │
                    │  Medical research    │
                    │      keyword         │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │      Streamlit       │
                    │      app.py          │
                    │                      │
                    │ Login / Signup       │
                    │ Search interface     │
                    │ Results UI            │
                    └──────┬─────────┬─────┘
                           │         │
              ┌────────────┘         └─────────────┐
              ▼                                    ▼
    ┌───────────────────┐                ┌───────────────────┐
    │   PubMed / NCBI   │                │      MySQL        │
    │ E-utilities API   │                │                   │
    │                   │                │ users             │
    │ Search PMIDs      │                │ searches          │
    │ Fetch articles    │                │ articles          │
    └─────────┬─────────┘                └───────────────────┘
              │
              ▼
    ┌──────────────────────┐
    │   Article dictionaries│
    │                      │
    │ PMID                  │
    │ Title                │
    │ Authors              │
    │ Journal              │
    │ Publication date     │
    │ Abstract             │
    └──────────┬───────────┘
               │
               ▼
    ┌──────────────────────────────┐
    │       RAG Ranking Engine     │
    │        rag_engine.py         │
    │                              │
    │ Query embedding              │
    │ Article embeddings           │
    │ Cosine similarity            │
    │ Author position weighting    │
    └──────────────┬───────────────┘
                   │
                   ▼
          ┌─────────────────┐
          │ Top 10 Authors  │
          │                 │
          │ Rank            │
          │ Author          │
          │ Role            │
          │ Score           │
          │ Matched paper   │
          └─────────────────┘
```

------------------------------------------------------------------------

# 3. Project structure

The project is organized around four main Python modules:

``` text
project/
│
├── app.py
├── pubmed_fetcher.py
├── rag_engine.py
└── db.py
```

The uploaded application file is named `app(1).py`, but its module
documentation identifies it as `apps.py`. For deployment, use the
filename configured as the Streamlit entry point (commonly `app.py`).

------------------------------------------------------------------------

# 4. File-by-file explanation

## 4.1 `app.py` --- Main Streamlit application

This is the **front end and application controller**.

It imports:

``` python
import streamlit as st
from pubmed_fetcher import search_pubmed, fetch_articles
from db import setup_database, save_search_results, create_user, verify_user
from rag_engine import get_top_doctors
```

The application initializes the database/tables and then displays the
user interface.

### Login and signup

The application starts with a Login and Sign Up interface.

For login:

``` python
verify_user(username, password)
```

is called.

If the credentials are valid:

``` python
st.session_state.logged_in = True
st.session_state.username = login_username
```

The application then reruns and shows the main search interface.

For signup, the application:

1.  Checks that username and password are present.
2.  Checks that the password confirmation matches.
3.  Calls `create_user()`.

Passwords are not stored directly. The database module hashes them using
bcrypt.

### Login gate

The application uses:

``` python
st.session_state.logged_in
```

to decide whether the user can access the search functionality.

If the user is not logged in:

``` python
st.stop()
```

halts the rest of the Streamlit script.

### Search interface

After login, the user sees a keyword input such as:

``` text
breast cancer
immunotherapy
diabetes
```

When Search is clicked:

``` python
pmid_list = search_pubmed(keyword)
```

is called.

Then:

``` python
articles = fetch_articles(pmid_list)
```

retrieves detailed article information.

The articles are saved:

``` python
save_search_results(keyword, articles)
```

Finally:

``` python
top_doctors = get_top_doctors(keyword, articles, top_n=10)
```

performs the semantic ranking.

The UI displays:

-   number of articles scanned
-   number of authors ranked
-   highest score
-   ranked author list
-   author role
-   matched paper title
-   relevance score

------------------------------------------------------------------------

# 5. `pubmed_fetcher.py` --- PubMed data collection

This module is responsible for communicating with PubMed.

It uses the NCBI E-utilities API:

``` text
https://eutils.ncbi.nlm.nih.gov/entrez/eutils
```

There are two important API operations.

## 5.1 ESearch

The application first calls PubMed's `esearch.fcgi` endpoint.

Conceptually:

``` text
User keyword
     ↓
PubMed ESearch
     ↓
List of PMIDs
```

For example:

``` text
"breast cancer"
```

might produce a list of PubMed IDs.

The function:

``` python
search_pubmed(keyword)
```

returns those IDs.

------------------------------------------------------------------------

## 5.2 EFetch

The application then passes those PMIDs to:

``` python
fetch_articles_xml(pmid_list)
```

which calls the PubMed `efetch.fcgi` endpoint.

The XML response contains detailed article information.

------------------------------------------------------------------------

## 5.3 XML parsing

The function:

``` python
parse_article(article_elem)
```

extracts:

``` text
PMID
Title
Journal
Publication date
Authors
Abstract
```

The returned Python dictionary has this structure:

``` python
{
    "pmid": "...",
    "title": "...",
    "authors": "...",
    "journal": "...",
    "pub_date": "...",
    "abstract": "..."
}
```

The authors are converted into a comma-separated string.

Abstract sections are combined into one string.

If an article does not have an abstract, the application uses:

``` text
No abstract available
```

------------------------------------------------------------------------

# 6. `rag_engine.py` --- Semantic ranking engine

This is the **AI/semantic-search component** of the project.

A key clarification:

> Despite the file being called a "RAG engine", this implementation does
> not generate an answer using a large language model.

Instead, it performs **semantic retrieval/ranking using embeddings**.

------------------------------------------------------------------------

## 6.1 Sentence Transformer model

The project loads:

``` python
SentenceTransformer("all-MiniLM-L6-v2")
```

This model converts text into numerical vectors called embeddings.

For example:

``` text
"heart disease treatment"
```

is converted into a vector representing its semantic meaning.

The same process is applied to article abstracts.

------------------------------------------------------------------------

# 7. How semantic similarity works

The application embeds:

``` text
User query
```

and each:

``` text
Article abstract
```

Then it compares the vectors using cosine similarity.

Conceptually:

``` text
Query
  │
  ▼
Embedding vector
  │
  │ compare
  ▼
Article abstract
  │
  ▼
Embedding vector
```

The cosine similarity function produces a score.

A score closer to `1` indicates that the vectors point in a more similar
direction.

The code then sorts articles from highest similarity to lowest
similarity.

This is better suited to semantic matching than simply checking whether
the exact keyword appears in the text.

------------------------------------------------------------------------

# 8. Why author position matters

After articles are ranked, the project does not simply count every
author equally.

The function:

``` python
author_position_weight(position, total_authors)
```

assigns different weights.

Current implementation:

  Author position     Weight
  ----------------- --------
  Sole author            1.0
  First author           1.0
  Last author            0.9
  Middle author          0.5

The idea is that first and senior/last authors can represent more
central research contributions.

------------------------------------------------------------------------

# 9. How the final author score is calculated

Suppose an article receives:

``` text
Semantic relevance = 0.80
```

If an author is the first author:

``` text
0.80 × 1.0 = 0.80
```

If the author is the last author:

``` text
0.80 × 0.9 = 0.72
```

If the author is a middle author:

``` text
0.80 × 0.5 = 0.40
```

The project then looks at all papers in the result set.

For each author, it keeps the author's **highest weighted score**.

Finally, authors are sorted by that score and the top 10 are returned.

------------------------------------------------------------------------

# 10. Example of the ranking process

Suppose PubMed returns:

``` text
Paper A
Relevance = 0.90

Authors:
Alice, Bob, Charlie
```

Weights:

``` text
Alice   → first author → 1.0
Bob     → middle      → 0.5
Charlie → last        → 0.9
```

Scores:

``` text
Alice   → 0.90
Bob     → 0.45
Charlie → 0.81
```

Another paper might contain Alice again:

``` text
Paper B
Relevance = 0.75

Alice is last author
```

Alice receives:

``` text
0.75 × 0.9 = 0.675
```

Her best score remains:

``` text
0.90
```

The final ranking therefore keeps:

``` text
Alice → 0.90
Charlie → 0.81
...
```

------------------------------------------------------------------------

# 11. `db.py` --- MySQL database layer

This module handles persistent storage.

It manages three tables.

## `users`

``` text
users
├── id
├── username
├── password_hash
└── created_at
```

The username is unique.

Passwords are stored as bcrypt hashes rather than plain text.

------------------------------------------------------------------------

## `searches`

``` text
searches
├── id
├── keyword
└── searched_at
```

Every search keyword can be recorded.

------------------------------------------------------------------------

## `articles`

``` text
articles
├── id
├── search_id
├── pmid
├── title
├── authors
├── journal
├── pub_date
└── abstract
```

Each article belongs to a search through:

``` text
articles.search_id
        ↓
searches.id
```

This is a foreign-key relationship.

------------------------------------------------------------------------

# 12. Database relationship

``` text
             searches
          ┌──────────────┐
          │ id           │
          │ keyword      │
          │ searched_at  │
          └──────┬───────┘
                 │
                 │ 1-to-many
                 ▼
          ┌──────────────┐
          │ articles     │
          │ id           │
          │ search_id    │
          │ pmid         │
          │ title        │
          │ authors      │
          │ journal      │
          │ pub_date     │
          │ abstract     │
          └──────────────┘


          ┌──────────────┐
          │ users        │
          │ id           │
          │ username     │
          │ password_hash│
          │ created_at   │
          └──────────────┘
```

------------------------------------------------------------------------

# 13. Signup security

When a user signs up, the application does:

``` python
bcrypt.hashpw(password_bytes, bcrypt.gensalt())
```

The database receives the resulting hash.

The original password is not stored.

During login, the application retrieves the stored hash and uses:

``` python
bcrypt.checkpw(...)
```

to verify the entered password.

------------------------------------------------------------------------

# 14. Complete application workflow

The complete process is:

``` text
1. User opens application
          │
          ▼
2. Login / Sign Up
          │
          ▼
3. MySQL verifies or creates account
          │
          ▼
4. User enters medical/research topic
          │
          ▼
5. app.py calls search_pubmed()
          │
          ▼
6. PubMed ESearch returns PMIDs
          │
          ▼
7. fetch_articles() calls EFetch
          │
          ▼
8. XML is parsed into article dictionaries
          │
          ├───────────────► MySQL stores search/articles
          │
          ▼
9. rag_engine.py receives query + articles
          │
          ▼
10. Query → embedding
          │
          ▼
11. Abstracts → embeddings
          │
          ▼
12. Cosine similarity
          │
          ▼
13. Articles ranked
          │
          ▼
14. Authors extracted
          │
          ▼
15. Author-position weights applied
          │
          ▼
16. Best score retained per author
          │
          ▼
17. Top 10 authors selected
          │
          ▼
18. Streamlit displays results
```

------------------------------------------------------------------------

# 15. Technologies used

  Technology                  Purpose
  --------------------------- ------------------------------------
  Python                      Main programming language
  Streamlit                   Web application UI
  PubMed / NCBI E-utilities   Medical research data
  MySQL                       Persistent database
  mysql-connector-python      Python/MySQL connection
  bcrypt                      Password hashing
  Sentence Transformers       Text embeddings
  all-MiniLM-L6-v2            Embedding model
  NumPy                       Vector and similarity calculations
  Requests                    HTTP/API requests
  ElementTree                 PubMed XML parsing
  python-dotenv               Environment variable loading

------------------------------------------------------------------------

# 16. Environment variables

The current code reads:

``` text
MYSQL_PASSWORD
PUMMED_API_KEY
```

from the environment.

There is also an important spelling detail in the current source:

``` python
API_KEY = os.getenv("PUMMED_API_KEY")
```

The variable is written as `PUMMED_API_KEY` in the code.

If you change it to `PUBMED_API_KEY`, make sure the environment variable
name is changed everywhere consistently.

------------------------------------------------------------------------

# 17. Running locally

Install the required Python packages used by the four modules:

``` bash
pip install streamlit requests mysql-connector-python bcrypt python-dotenv sentence-transformers numpy
```

Then configure your environment variables.

For example:

``` text
MYSQL_PASSWORD=your_mysql_password
PUMMED_API_KEY=your_ncbi_api_key
```

Make sure MySQL is running and the database is available.

Then run the Streamlit application:

``` bash
streamlit run app.py
```

------------------------------------------------------------------------

# 18. Deployment

For cloud deployment, the MySQL server must be reachable from the cloud
application.

Do **not** use:

``` text
localhost
```

for a cloud-hosted application when the MySQL database is running on
your personal computer.

A managed MySQL service such as Aiven can be used instead.

The application should receive the remote database connection details
through Streamlit Secrets/environment configuration.

Example:

``` toml
MYSQL_HOST = "your-mysql-host"
MYSQL_PORT = 3306
MYSQL_USER = "your-mysql-user"
MYSQL_PASSWORD = "your-mysql-password"
MYSQL_DATABASE = "pubmed_app"
```

The exact host, port, username, and password depend on the MySQL
provider.

------------------------------------------------------------------------

# 19. Important deployment consideration

The current `db.py` was originally written for a local MySQL
installation.

It currently contains:

``` python
DB_HOST = "localhost"
DB_USER = "root"
DB_NAME = "pubmed_app"
```

and attempts to create the database:

``` sql
CREATE DATABASE IF NOT EXISTS pubmed_app
```

For a managed cloud database, it is generally better to create the
database through the provider and have the application connect directly
to it.

The table creation logic can remain in the application if the database
user has the required permissions.

------------------------------------------------------------------------

# 20. Error-handling behavior

The project contains basic error handling.

PubMed HTTP errors return an empty result rather than crashing the
application.

Invalid XML responses are also handled.

Missing abstracts are skipped by the ranking engine because semantic
similarity cannot be meaningfully calculated without article text.

The Streamlit UI shows messages such as:

``` text
Please enter a keyword.
No articles found.
Found articles, but couldn't rank any authors.
Invalid username or password.
```

------------------------------------------------------------------------

# 21. Current limitations

The current implementation is a useful prototype, but it has several
limitations.

### 1. "Doctors" are actually PubMed authors

The system does not verify:

-   medical license
-   specialty
-   hospital affiliation
-   current employment
-   clinical practice
-   geographic location

It ranks authors of relevant research papers.

### 2. Author names are treated as plain text

Authors are stored and split using commas.

This can cause problems with:

-   name ambiguity
-   identical names
-   different formatting
-   special author-name structures

### 3. The system uses the best paper score for each author

An author with many relevant papers is not necessarily ranked higher
simply because they have many papers.

The implementation keeps the author's highest weighted score.

### 4. No LLM-generated explanation

The RAG engine uses embeddings and similarity but does not generate
natural-language explanations.

### 5. Embeddings are calculated at search time

The application embeds the query and article abstracts when the ranking
function runs.

For larger datasets, pre-computed embeddings or a vector database would
be more scalable.

### 6. The embedding model is downloaded when first loaded

The model:

``` text
all-MiniLM-L6-v2
```

is loaded when `rag_engine.py` is imported.

The first run may therefore take longer.

### 7. PubMed result count inconsistency

The source comment describes fetching up to 50 articles in several
places, while the actual constant is:

``` python
MAX_RESULTS = 100
```

and `search_pubmed()` uses that value by default.

Therefore, the current implementation requests up to 100 PubMed results
unless a different value is passed.

------------------------------------------------------------------------

# 22. Is this really RAG?

The project calls `rag_engine.py` a RAG engine, but technically it is
closer to:

**semantic retrieval + ranking**

rather than a complete Retrieval-Augmented Generation pipeline.

Traditional RAG usually looks like:

``` text
User question
     ↓
Retrieve relevant documents
     ↓
Send retrieved documents to an LLM
     ↓
Generate an answer
```

This project currently does:

``` text
User query
     ↓
Generate embedding
     ↓
Retrieve/rank relevant article abstracts
     ↓
Rank authors
     ↓
Display ranked results
```

There is no LLM generation step.

A future version could add an LLM to explain why each researcher is
relevant.

------------------------------------------------------------------------

# 23. Possible future improvements

Potential improvements include:

-   Add researcher profiles.
-   Add institution/hospital information.
-   Add PubMed links for papers.
-   Add publication counts.
-   Add recent-publication weighting.
-   Add specialty detection.
-   Add geographic filtering.
-   Resolve author identities using ORCID.
-   Store embeddings in a vector database.
-   Add an LLM explanation layer.
-   Add pagination for PubMed results.
-   Add search history to the UI.
-   Add user-specific search history.
-   Improve database error messages.
-   Add stronger username/password validation.
-   Add password reset functionality.
-   Add caching for repeated searches.
-   Pre-compute article embeddings.
-   Use a proper author identity resolution strategy.

------------------------------------------------------------------------

# 24. Example user journey

### Step 1

User creates an account:

``` text
Username: alfie
Password: ********
```

### Step 2

User logs in.

### Step 3

User searches:

``` text
breast cancer immunotherapy
```

### Step 4

PubMed is queried.

### Step 5

The application receives article information.

### Step 6

The articles are saved in MySQL.

### Step 7

The RAG/semantic ranking engine compares the query against article
abstracts.

### Step 8

Authors receive weighted relevance scores.

### Step 9

The application displays something conceptually like:

``` text
1. Researcher A
   First author
   Relevance score: 0.842

   Paper: ...

2. Researcher B
   Senior/last author
   Relevance score: 0.817

   Paper: ...

3. Researcher C
   Co-author
   Relevance score: 0.694

   Paper: ...
```

------------------------------------------------------------------------

# 25. Summary

Top Doctors Finder is a **medical research author discovery
application**.

Its main pipeline is:

``` text
Streamlit
   ↓
User authentication
   ↓
Medical topic
   ↓
PubMed search
   ↓
Article retrieval
   ↓
MySQL storage
   ↓
Sentence Transformer embeddings
   ↓
Cosine similarity
   ↓
Author-position weighting
   ↓
Top 10 PubMed authors
   ↓
Streamlit results
```

The core idea is to move from simple keyword search toward **semantic
relevance**, while using author position as an additional signal when
determining which researchers are most strongly associated with the
searched topic.
