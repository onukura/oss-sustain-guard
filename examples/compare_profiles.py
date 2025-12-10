"""
Example: Comparing scoring profiles for a real repository.

This script demonstrates how to use different scoring profiles
to evaluate the same project from different perspectives.
"""

from oss_sustain_guard.core import (
    Metric,
    compare_scoring_profiles,
    compute_weighted_total_score,
)

# Example metrics from a hypothetical analysis
# (In real usage, these would come from analyze_repository())
example_metrics = [
    # Maintainer Health (25% in balanced)
    Metric(
        "Contributor Redundancy",
        15,
        20,
        "Good: 8 contributors with >10% commits each",
        "Low",
    ),
    Metric("Maintainer Retention", 8, 10, "Good: 80% maintainer retention", "Low"),
    Metric(
        "Contributor Attraction",
        7,
        10,
        "Good: 4 new contributors in last 6 months",
        "Low",
    ),
    Metric("Contributor Retention", 8, 10, "Good: 80% contributor retention", "Low"),
    Metric("Organizational Diversity", 6, 10, "Good: 3 organizations detected", "Low"),
    # Development Activity (20% in balanced)
    Metric("Recent Activity", 18, 20, "Excellent: Last commit 2 days ago", "None"),
    Metric("Release Rhythm", 9, 10, "Excellent: Last release 45 days ago", "None"),
    Metric("Build Health", 5, 5, "Excellent: CI passing on all workflows", "None"),
    Metric(
        "Change Request Resolution", 8, 10, "Good: 82% PRs merged within 7 days", "Low"
    ),
    # Community Engagement (20% in balanced)
    Metric("Issue Responsiveness", 4, 5, "Excellent: Avg response 18h", "None"),
    Metric("PR Acceptance Ratio", 8, 10, "Excellent: 85% PR acceptance rate", "None"),
    Metric("PR Responsiveness", 4, 5, "Excellent: Avg PR first response 20h", "None"),
    Metric("Review Health", 9, 10, "Excellent: Avg time to first review 22h", "None"),
    Metric(
        "Issue Resolution Duration", 8, 10, "Good: Avg issue resolution 12 days", "Low"
    ),
    # Project Maturity (15% in balanced)
    Metric(
        "Documentation Presence", 10, 10, "Excellent: 5/5 documentation signals", "None"
    ),
    Metric("Code of Conduct", 5, 5, "Excellent: Code of Conduct present", "None"),
    Metric("License Clarity", 5, 5, "Excellent: MIT (OSI-approved)", "None"),
    Metric("Project Popularity", 8, 10, "Popular: ⭐ 750 stars, 45 watchers", "None"),
    Metric("Fork Activity", 4, 5, "Good: 85 forks, 2 recent", "None"),
    # Security & Funding (20% in balanced)
    Metric("Security Signals", 10, 15, "Good: Security policy + no alerts", "Low"),
    Metric("Funding Signals", 3, 10, "Observe: Limited funding signals", "Medium"),
]


def main():
    print("=" * 80)
    print("Scoring Profile Comparison Example")
    print("=" * 80)
    print()

    # Calculate individual profile scores
    print("Individual Profile Scores:")
    print("-" * 80)

    profiles = [
        "balanced",
        "security_first",
        "contributor_experience",
        "long_term_stability",
    ]
    scores = {}

    for profile in profiles:
        score = compute_weighted_total_score(example_metrics, profile)
        scores[profile] = score
        print(f"  {profile:25s}: {score:3d}/100")

    print()
    print("=" * 80)
    print()

    # Detailed comparison
    print("Detailed Profile Comparison:")
    print("-" * 80)

    comparison = compare_scoring_profiles(example_metrics)

    for profile_key in [
        "balanced",
        "security_first",
        "contributor_experience",
        "long_term_stability",
    ]:
        data = comparison[profile_key]
        print(f"\n{data['name']} ({profile_key})")
        print(f"  Score: {data['total_score']}/100")
        print(f"  Description: {data['description']}")
        print("\n  Category Weights:")
        for category, weight in data["weights"].items():
            category_score = data["category_scores"][category]
            contribution = category_score * weight
            print(
                f"    {category:25s}: {weight:5.1%} × {category_score:5.1f} = {contribution:5.1f}"
            )

    print()
    print("=" * 80)
    print()

    # Analysis
    print("Analysis:")
    print("-" * 80)

    max_profile = max(scores.items(), key=lambda x: x[1])
    min_profile = min(scores.items(), key=lambda x: x[1])

    print(f"\n  Highest score: {max_profile[0]} ({max_profile[1]}/100)")
    print(f"  Lowest score:  {min_profile[0]} ({min_profile[1]}/100)")
    print(f"  Range:         {max_profile[1] - min_profile[1]} points")

    print("\n  Key Observations:")
    print("    • Strong community engagement (Issue Responsiveness: 4/5)")
    print("    • Excellent documentation (all signals present)")
    print("    • Active development (recent commits and releases)")
    print("    • Limited funding signals (3/10) - affects security_first score")

    print("\n  Recommendations:")
    if scores["security_first"] < 75:
        print(f"    ⚠️  Security-first score ({scores['security_first']}) suggests:")
        print("        - Consider adding more funding signals")
        print("        - Enhance security posture (currently 10/15)")

    if scores["contributor_experience"] >= 85:
        print(
            f"    ✅ Excellent contributor experience ({scores['contributor_experience']}/100)"
        )
        print("        - Great project for first-time contributors")

    if scores["long_term_stability"] >= 80:
        print(
            f"    ✅ Strong long-term stability ({scores['long_term_stability']}/100)"
        )
        print("        - Good choice for long-term dependencies")

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
