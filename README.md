# 🩺 Top Doctors Finder

Top Doctors Finder is a Streamlit web app that searches PubMed for a medical or research topic and ranks the **authors** of the most relevant papers — helping you discover researchers/experts associated with a given topic.

> **Note:** The app ranks *PubMed paper authors*. It does **not** verify medical licenses, specialties, or current clinical practice. Think of "doctor" here as "research author/expert linked to relevant publications."

---

## ✨ What it does

Instead of manually opening dozens of PubMed papers to see who wrote them, this app automates the process:

1. You enter a topic (e.g. `breast cancer`, `immunotherapy`, `diabetes`).
2. It searches PubMed and fetches matching articles (title, authors, journal, date, abstract).
3. It saves the results to a MySQL database.
4. It converts your query and each article's abstract into semantic embeddings.
5. It scores relevance using cosine similarity.
6. It weights authors differently depending on their position (first/last authors count more than middle authors).
7. It returns the **top 10 ranked authors**, along with their role, score, and the paper that produced their best score.

---

## 🧱 Tech Stack

| Technology | Purpose |
|---|---|
| Python | Core language |
| Streamlit | Web UI |
| PubMed / NCBI E-utilities | Medical research data source |
| MySQL | Stores users, searches, articles |
| mysql-connector-python | MySQL connectivity |
| bcrypt | Password hashing |
| Sentence Transformers (`all-MiniLM-L6-v2`) | Text embeddings |
| NumPy | Similarity calculations |
| Requests | HTTP calls to PubMed |
| ElementTree | Parses PubMed XML |
| python-dotenv | Loads environment variables |

---

## 📁 Project Structure

```
project/
│
├── app.py             # Streamlit front end & app controller
├── pubmed_fetcher.py  # PubMed search + article fetching/parsing
├── rag_engine.py      # Embeddings, similarity scoring, author ranking
└── db.py              # MySQL setup, users, searches, articles
```

> The Streamlit entry point should be named `app.py` for deployment.

---

## ⚙️ How it works (high level)

```
User → Streamlit (login/search) → PubMed (ESearch + EFetch)
     → Article data → MySQL (stored)
     → Query + abstracts → Embeddings → Cosine similarity
     → Author position weighting → Best score per author
     → Top 10 authors → Displayed in Streamlit
```

**Author position weights** used when scoring:

| Position | Weight |
|---|---|
| Sole author | 1.0 |
| First author | 1.0 |
| Last author | 0.9 |
| Middle author | 0.5 |

An author's **final score** = (semantic relevance of the paper) × (position weight). If an author appears in multiple papers, their **highest** weighted score is kept.

---

## 🚀 Getting Started

### 1. Install dependencies

```bash
pip install streamlit requests mysql-connector-python bcrypt python-dotenv sentence-transformers numpy
```

### 2. Set up environment variables

Create a `.env` file:

```
MYSQL_PASSWORD=your_mysql_password
PUMMED_API_KEY=your_ncbi_api_key
```

> ⚠️ The code currently reads the NCBI API key from a variable named `PUMMED_API_KEY` (note the spelling). If you rename it to `PUBMED_API_KEY`, update it consistently everywhere in the code.

### 3. Set up MySQL

Make sure a MySQL server is running and reachable. By default, the app is configured for local use:

```
DB_HOST = "localhost"
DB_USER = "root"
DB_NAME = "pubmed_app"
```

### 4. Run the app

```bash
streamlit run app.py
```

---

## ☁️ Deploying to the cloud

If you deploy this app to a cloud platform, your MySQL database **cannot** be `localhost` on your personal machine — the cloud app needs a reachable database.

Use a managed MySQL provider (e.g. Aiven, PlanetScale, RDS) and pass the connection details via Streamlit Secrets or environment variables:

```
MYSQL_HOST = "your-mysql-host"
MYSQL_PORT = 3306
MYSQL_USER = "your-mysql-user"
MYSQL_PASSWORD = "your-mysql-password"
MYSQL_DATABASE = "pubmed_app"
```

Table creation logic can stay in the app as long as the database user has the right permissions — but for managed databases, it's often cleaner to create the database via the provider first.

---

## 🗄️ Database Schema

**users**
- `id`, `username` (unique), `password_hash` (bcrypt), `created_at`

**searches**
- `id`, `keyword`, `searched_at`

**articles**
- `id`, `search_id` (FK → searches.id), `pmid`, `title`, `authors`, `journal`, `pub_date`, `abstract`

---

## 🔐 Authentication

- Passwords are hashed with `bcrypt` before storage — plain text passwords are never saved.
- Login verifies the entered password against the stored hash using `bcrypt.checkpw()`.

---

## ⚠️ Current Limitations

- **"Doctors" are really just PubMed authors** — no license, specialty, or affiliation verification.
- **Author names are plain text** — no disambiguation for identical/similar names.
- **Best-score ranking** — an author with many relevant papers isn't ranked higher just for volume; only their top score counts.
- **No LLM explanation layer** — it's semantic retrieval + ranking, not full RAG (no generated natural-language explanation).
- **Embeddings computed at search time** — not pre-computed, which may not scale well for large datasets.
- **First run may be slow** — the embedding model (`all-MiniLM-L6-v2`) downloads on first load.
- **Result limit** — the app requests up to 100 PubMed results by default (`MAX_RESULTS = 100`).

---

## 🔭 Possible Future Improvements

- Researcher profiles & institution/hospital info
- Direct PubMed links per paper
- Publication counts & recent-publication weighting
- Specialty & geographic filtering
- ORCID-based author identity resolution
- Vector database for pre-computed embeddings
- LLM-generated explanations for rankings
- Pagination & search history
- Password reset & stronger validation
- Caching for repeated searches

---

## 📝 License

Add your preferred license here (e.g. MIT).