"""
rag_engine.py
--------------
RAG (Retrieval-Augmented Generation) ranking engine.

Given a set of articles and a user query, this ranks the articles
by semantic relevance to the query (not just keyword matching),
then extracts the top 10 authors from the most relevant articles -
weighting first/last authors higher than middle co-authors, since
that reflects how research contribution is signaled in papers.

Uses sentence-transformers (a local, free embedding model) -
no API key, no internet required after the first model download.
"""

from sentence_transformers import SentenceTransformer
import numpy as np

# Load the embedding model once when this module is imported.
# 'all-MiniLM-L6-v2' is small, fast, and good enough for this use case.
# The first time this runs, it downloads the model (~80MB) automatically.
_model = SentenceTransformer("all-MiniLM-L6-v2")


def get_embedding(text):
    """
    Converts a piece of text into a vector (list of numbers) that
    captures its meaning. Similar meanings -> similar vectors.
    """
    return _model.encode(text)


def cosine_similarity(vec_a, vec_b):
    """
    Measures how 'close' two vectors are in meaning, from -1 to 1
    (1 = identical meaning, 0 = unrelated, -1 = opposite).
    This is the standard way to compare embeddings.
    """
    vec_a = np.array(vec_a)
    vec_b = np.array(vec_b)
    return np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b))


def rank_articles_by_relevance(query, articles):
    """
    Embeds the query and every article's abstract, scores each article
    by similarity to the query, and returns the articles sorted
    best-match-first, each tagged with its score.

    Takes: query (string), articles (list of dicts with an 'abstract' key)
    Returns: list of dicts, same as input but with an added 'score' key,
             sorted highest score first.
    """
    if not articles:
        return []

    # Embed the user's query once
    query_vector = get_embedding(query)

    scored_articles = []
    for article in articles:
        # Skip meaningfully comparing articles with no real abstract text
        abstract = article.get("abstract", "")
        if not abstract or abstract == "No abstract available":
            continue

        article_vector = get_embedding(abstract)
        score = cosine_similarity(query_vector, article_vector)

        # Copy the article dict and add its score, so we don't mutate the original
        scored_article = dict(article)
        scored_article["score"] = float(score)
        scored_articles.append(scored_article)

    # Sort so the most relevant articles come first
    scored_articles.sort(key=lambda a: a["score"], reverse=True)
    return scored_articles


def author_position_weight(position, total_authors):
    """
    Returns a weight (0-1) based on WHERE an author sits in the author list.

    Why this matters: in research papers, position signals contribution.
    - First author: usually did the hands-on research -> full credit
    - Last author (when there are 3+ authors): usually the senior
      researcher/lab lead who oversaw the work -> full credit
    - Everyone in between: contributed, but less centrally -> partial credit
    - Solo author: full credit, obviously

    position is 0-indexed (0 = first author).
    """
    if total_authors == 1:
        return 1.0
    if position == 0:                      # first author
        return 1.0
    if position == total_authors - 1:      # last author
        return 0.9
    return 0.5                             # middle authors


def get_top_doctors(query, articles, top_n=10):
    """
    Takes the relevance-ranked articles and extracts a ranked list of
    authors. Each author's score = the highest WEIGHTED relevance score
    among all their papers in this result set, where the weight depends
    on their author position (see author_position_weight above).

    Returns: list of dicts like
        {"author": "Jane Smith", "score": 0.83, "matched_title": "...",
         "role": "First author"}
    sorted best match first, limited to top_n.
    """
    ranked_articles = rank_articles_by_relevance(query, articles)

    # Track the best WEIGHTED score seen so far for each author
    author_best = {}

    for article in ranked_articles:
        authors_str = article.get("authors", "")
        if not authors_str or authors_str == "No authors listed":
            continue

        author_names = [a.strip() for a in authors_str.split(",")]
        total = len(author_names)

        for position, name in enumerate(author_names):
            weight = author_position_weight(position, total)
            weighted_score = article["score"] * weight

            # Label for the UI, so the user can see WHY someone ranked where they did
            if total == 1:
                role = "Sole author"
            elif position == 0:
                role = "First author"
            elif position == total - 1:
                role = "Senior/last author"
            else:
                role = "Co-author"

            # Keep this record only if it's better than what we've stored
            # for this author so far (we can't just take the FIRST time we
            # see them anymore, since weighting can change the ordering)
            existing = author_best.get(name)
            if existing is None or weighted_score > existing["score"]:
                author_best[name] = {
                    "author": name,
                    "score": weighted_score,
                    "matched_title": article["title"],
                    "role": role
                }

    # Convert the dict of authors into a sorted list, best weighted score first
    top_authors = sorted(author_best.values(), key=lambda a: a["score"], reverse=True)
    return top_authors[:top_n]


# --- Terminal-only test block ---
if __name__ == "__main__":
    from pubmed_fetcher import search_pubmed, fetch_articles

    query = input("Enter a topic to find top doctors for: ")
    print(f"\nFetching articles for '{query}'...")
    pmid_list = search_pubmed(query)
    articles = fetch_articles(pmid_list)

    print("Ranking with RAG engine...")
    top_doctors = get_top_doctors(query, articles)

    print(f"\nTop {len(top_doctors)} authors by relevance:\n")
    for i, doc in enumerate(top_doctors, start=1):
        print(f"{i}. {doc['author']}  ({doc['role']}, score: {doc['score']:.3f})")
        print(f"   Most relevant paper: {doc['matched_title']}")