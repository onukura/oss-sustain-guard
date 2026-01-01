"""Tests for organizational diversity metric."""

from oss_sustain_guard.metrics.organizational_diversity import (
    check_organizational_diversity,
)


class TestOrganizationalDiversity:
    """Test organizational diversity metric."""

    def test_no_commit_history(self):
        """Test with no commit history."""
        repo_data = {"defaultBranchRef": None}
        result = check_organizational_diversity(repo_data)
        assert result.score == 5
        assert result.max_score == 10
        assert "Commit history data not available" in result.message
        assert result.risk == "None"

    def test_highly_diverse(self):
        """Test highly diverse organizations."""
        repo_data = {
            "defaultBranchRef": {
                "target": {
                    "history": {
                        "edges": [
                            {
                                "node": {
                                    "author": {
                                        "user": {
                                            "login": "user1",
                                            "company": "Company A",
                                        },
                                        "email": "user1@companya.com",
                                    }
                                }
                            },
                            {
                                "node": {
                                    "author": {
                                        "user": {
                                            "login": "user2",
                                            "company": "Company B",
                                        },
                                        "email": "user2@companyb.com",
                                    }
                                }
                            },
                            {
                                "node": {
                                    "author": {
                                        "user": {
                                            "login": "user3",
                                            "company": "Company C",
                                        },
                                        "email": "user3@companyc.com",
                                    }
                                }
                            },
                            {
                                "node": {
                                    "author": {
                                        "user": {
                                            "login": "user4",
                                            "company": "Company D",
                                        },
                                        "email": "user4@companyd.com",
                                    }
                                }
                            },
                            {
                                "node": {
                                    "author": {
                                        "user": {
                                            "login": "user5",
                                            "company": "Company E",
                                        },
                                        "email": "user5@companye.com",
                                    }
                                }
                            },
                        ]
                    }
                }
            }
        }
        result = check_organizational_diversity(repo_data)
        assert result.score == 10
        assert result.max_score == 10
        assert "Excellent" in result.message
        assert result.risk == "None"

    def test_good_diversity(self):
        """Test good organizational diversity."""
        repo_data = {
            "defaultBranchRef": {
                "target": {
                    "history": {
                        "edges": [
                            {
                                "node": {
                                    "author": {
                                        "user": {
                                            "login": "user1",
                                            "company": "Company A",
                                        },
                                        "email": "user1@companya.com",
                                    }
                                }
                            },
                            {
                                "node": {
                                    "author": {
                                        "user": {
                                            "login": "user2",
                                            "company": "Company B",
                                        },
                                        "email": "user2@companyb.com",
                                    }
                                }
                            },
                            {
                                "node": {
                                    "author": {
                                        "user": {
                                            "login": "user3",
                                            "company": "Company C",
                                        },
                                        "email": "user3@companyc.com",
                                    }
                                }
                            },
                        ]
                    }
                }
            }
        }
        result = check_organizational_diversity(repo_data)
        assert result.score == 7
        assert result.max_score == 10
        assert "Good" in result.message
        assert result.risk == "Low"

    def test_moderate_diversity(self):
        """Test moderate organizational diversity."""
        repo_data = {
            "defaultBranchRef": {
                "target": {
                    "history": {
                        "edges": [
                            {
                                "node": {
                                    "author": {
                                        "user": {
                                            "login": "user1",
                                            "company": "Company A",
                                        },
                                        "email": "user1@companya.com",
                                    }
                                }
                            },
                            {
                                "node": {
                                    "author": {
                                        "user": {
                                            "login": "user2",
                                            "company": "Company B",
                                        },
                                        "email": "user2@companyb.com",
                                    }
                                }
                            },
                        ]
                    }
                }
            }
        }
        result = check_organizational_diversity(repo_data)
        assert result.score == 4
        assert result.max_score == 10
        assert "Moderate" in result.message
        assert result.risk == "Medium"

    def test_single_organization(self):
        """Test single organization dependency."""
        repo_data = {
            "defaultBranchRef": {
                "target": {
                    "history": {
                        "edges": [
                            {
                                "node": {
                                    "author": {
                                        "user": {
                                            "login": "user1",
                                            "company": "Company A",
                                        },
                                        "email": "user1@companya.com",
                                    }
                                }
                            },
                            {
                                "node": {
                                    "author": {
                                        "user": {
                                            "login": "user2",
                                            "company": "Company A",
                                        },
                                        "email": "user2@companya.com",
                                    }
                                }
                            },
                        ]
                    }
                }
            }
        }
        result = check_organizational_diversity(repo_data)
        assert result.score == 2
        assert result.max_score == 10
        assert "Single organization dominates" in result.message
        assert result.risk == "High"

    def test_personal_project(self):
        """Test personal project with no organizational data."""
        repo_data = {
            "defaultBranchRef": {
                "target": {
                    "history": {
                        "edges": [
                            {
                                "node": {
                                    "author": {
                                        "user": {"login": "user1", "company": None},
                                        "email": "user1@gmail.com",
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
        result = check_organizational_diversity(repo_data)
        assert result.score == 5
        assert result.max_score == 10
        assert "Unable to determine organizational diversity" in result.message
        assert result.risk == "None"
