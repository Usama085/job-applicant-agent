from pathlib import Path

from job_agent.main import load_search_queries


def test_load_search_queries_can_force_lahore_locations(tmp_path: Path):
    config = tmp_path / "search_queries.yaml"
    config.write_text(
        """
queries:
  - title: "DevOps Engineer"
    locations:
      - "Karachi"
      - "Islamabad"
    experience_max_years: 3
    remote_ok: true
""",
        encoding="utf-8",
    )

    queries = load_search_queries(config, forced_locations=["Lahore"])

    assert len(queries) == 1
    assert queries[0].title == "DevOps Engineer"
    assert queries[0].location == "Lahore"
