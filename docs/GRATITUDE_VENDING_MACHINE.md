# Gratitude Vending Machine

The **Gratitude Vending Machine** is a unique feature in OSS Sustain Guard that helps you discover and support community-driven open-source projects that need your help the most.

## 🎯 Purpose

Open-source maintainers often work without compensation, dedicating their time to projects that power millions of applications. The Gratitude Vending Machine makes it easy to:

1. **Discover** which dependencies need support most urgently
2. **Understand** the sustainability challenges they face
3. **Support** maintainers directly through funding links

## 🚀 How It Works

The command analyzes your cached dependencies and calculates a **support priority score** for each community-driven project based on:

### Priority Calculation

```
Priority = (100 - Health Score) + (10 - Contributor Redundancy) + (10 - Commit Author Continuity)
```

**Higher priority = More support needed**

- **Health Score** (0-100): Overall project sustainability
- **Contributor Redundancy** (0-10): Distribution of contributions (lower = single-maintainer concentration)
- **Commit Author Continuity** (0-10): Continuity of the project's principal committers

### Filtering Criteria

Only projects that meet ALL of these criteria are shown:

✅ **Community-driven** - Not corporate-backed (we respect different sustainability models)
✅ **Has funding links** - At least one way to support (GitHub Sponsors, Open Collective, Patreon, etc.)
✅ **In your dependencies** - Projects you actually use (from cached analysis)

## 📖 Usage

### Basic Usage

```bash
# Show top 3 projects that need support
os4g gratitude

# Show top 5 projects
os4g gratitude --top 5
```

### Example Output

```text
🎁 Gratitude Vending Machine
Loading community projects that could use your support...

Top 3 projects that would appreciate your support:

1. rich (python)
   Repository: https://github.com/Textualize/rich
   Health Score: 77/100 (Monitor)
   Contributor Redundancy: 10/10
   Commit Author Continuity: 10/10
   💝 Support options:
      • GITHUB: https://github.com/willmcgugan

2. pytest (python)
   Repository: https://github.com/pytest-dev/pytest
   Health Score: 78/100 (Monitor)
   Contributor Redundancy: 8/10
   Commit Author Continuity: 10/10
   💝 Support options:
      • GITHUB: https://github.com/pytest-dev
      • TIDELIFT: https://tidelift.com/funding/github/pypi/pytest
      • OPEN_COLLECTIVE: https://opencollective.com/pytest

3. typer (python)
   Repository: https://github.com/fastapi/typer
   Health Score: 76/100 (Monitor)
   Contributor Redundancy: 8/10
   Commit Author Continuity: 10/10
   💝 Support options:
      • GITHUB: https://github.com/tiangolo

Would you like to open a funding link?
Enter project number (1-3) to open funding link, or 'q' to quit:
```

### Interactive Actions

After viewing the list, you can:

- **Enter a number** (1-3): Open funding links for that project
- **Enter 'q'**: Quit without taking action
- **Ctrl+C**: Cancel at any time

When you select a project:

- **Single funding link**: Opens directly in your browser
- **Multiple funding links**: Shows platform menu to choose from

## 🌟 What Makes This Special

### 1. Smart Prioritization

Unlike simple popularity metrics, the Gratitude Vending Machine considers:

- **Actual need**: Projects with lower health scores get higher priority
- **Contributor concentration**: Single-maintainer projects are highlighted
- **Maintainer capacity**: Projects with overworked maintainers rank higher

### 2. Community Focus

- ✅ Shows **community-driven** projects (volunteers, small teams)
- ❌ Excludes **corporate-backed** projects (different sustainability model)

This respects the fact that corporate-backed projects have different support structures.

### 3. One-Click Support

No need to manually search for funding links:

- Opens directly in your default browser
- Supports GitHub Sponsors, Open Collective, Patreon, Tidelift, and more
- Multiple platforms? Interactive menu to choose

### 4. Awareness & Education

Each project shows:

- **Health Score**: Overall sustainability (0-100)
- **Contributor Redundancy**: Single-maintainer concentration signal
- **Commit Author Continuity**: Whether the principal committers are still active
- **Repository URL**: Link to the project

This helps you understand **why** a project needs support.

## 🎨 Design Philosophy

The Gratitude Vending Machine embodies our core belief:

> **Open-source sustainability requires both awareness and action.**

We designed this feature to:

- 🌱 **Raise awareness** - Show the challenges maintainers face
- 🤝 **Make support easy** - Remove friction from giving back
- 💝 **Encourage gratitude** - Frame support as appreciation, not obligation
- 📊 **Stay transparent** - Show metrics, not judgments
- 🎯 **Respect differences** - Acknowledge different project models

## ❓ FAQ

### Q: Why don't I see corporate-backed projects?

Corporate-backed projects (e.g., maintained by large organizations like Google, Microsoft, etc.) have different sustainability models. They typically don't rely on community donations, so we exclude them to focus on projects that truly need direct financial support.

### Q: Why is a "healthy" project shown?

Even projects with high health scores (80+) may appear if they:

- Have low contributor redundancy (single-maintainer concentration)
- Have declining maintainer retention (recent contributor loss)
- Have significant dependency impact

Health Score is just one factor—the algorithm considers multiple sustainability dimensions.

### Q: Can I support projects without opening funding links?

Yes! Supporting doesn't always mean money. You can also:

- Contribute code, documentation, or tests
- Triage issues or review pull requests
- Spread the word about the project
- Thank the maintainers in issues or social media

The Gratitude Vending Machine is about **awareness**, not just donations.

### Q: How often should I run this?

We recommend running it:

- **Monthly**: After adding new dependencies
- **Quarterly**: As part of dependency review
- **Yearly**: To celebrate maintainers during events like [Maintainer Month](https://maintainermonth.github.com/)

### Q: What if I don't have funding to give?

That's completely okay! Even running this command helps by:

1. Raising awareness about the projects you depend on
2. Reminding you who keeps your code running
3. Encouraging you to contribute in non-financial ways

Open-source is built on many forms of contribution—not just money.

### Q: Why "Vending Machine"?

The name reflects our philosophy:

- **Simple & familiar**: Like a vending machine, it's easy to use
- **Direct delivery**: One click to support
- **No judgment**: Choose what you want, when you want
- **Delightful**: A bit whimsical to make giving back fun

## 🛠️ Technical Details

### Data Source

The command uses your **local cache** (`~/.cache/oss-sustain-guard`) which stores analysis data for:

- Packages you've analyzed with `os4g check`
- Pre-computed database entries (if available)

**Note**: If cache is empty or disabled, you'll see a message to run analysis first.

### Supported Funding Platforms

The command recognizes funding links from:

- GitHub Sponsors
- Open Collective
- Patreon
- Tidelift
- Thanks.dev
- Ko-fi
- Buy Me a Coffee
- Custom URLs (from `FUNDING.yml`)

### Community vs. Corporate Detection

Projects are classified as "community-driven" if:

- Owner is an individual user (not an organization), OR
- Owner is an organization with certain patterns (e.g., community-focused foundations)
- NOT backed by major corporations (Google, Microsoft, Meta, etc.)

This classification is heuristic-based and stored in the analysis data.

## 🤝 Contributing

Have ideas to improve the Gratitude Vending Machine?

- **Priority algorithm**: Suggest better ways to calculate support priority
- **Funding platforms**: Add support for new platforms
- **UI/UX**: Improve the interactive experience
- **Documentation**: Help others discover and use this feature

See [Contributing Guide](GETTING_STARTED.md) for details.

## 📚 Related Documentation

- [Getting Started](GETTING_STARTED.md)
- [Scoring Profiles](SCORING_PROFILES_GUIDE.md)
- [CHAOSS Metrics Alignment](./CHAOSS_METRICS_ALIGNMENT_VALIDATION.md)

---

**Thank you for supporting open-source maintainers!** 💝

Every contribution—whether financial, code, or just awareness—helps make the OSS ecosystem more sustainable.
