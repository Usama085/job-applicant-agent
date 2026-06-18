from job_agent.matching.keyword_extractor import KeywordExtractor


def test_extract_known_technical_keywords():
    extractor = KeywordExtractor()
    keywords = extractor.extract(
        "DevOps Engineer with Python, Docker, Kubernetes, AWS, CI/CD and Terraform."
    )

    assert "devops" in keywords
    assert "python" in keywords
    assert "docker" in keywords
    assert "kubernetes" in keywords
    assert "terraform" in keywords


def test_extract_returns_sorted_unique_keywords():
    extractor = KeywordExtractor()
    keywords = extractor.extract("Docker docker DOCKER Kubernetes")

    assert keywords == ["docker", "kubernetes"]
