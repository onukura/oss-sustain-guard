# GitLab Provider Migration Plan

## 🎯 目的

Refactor metrics to be VCS-agnostic so the GitLab provider can deliver accurate scores.

## 📊 現在の状況

### 実装済み
- ✅ GitLab GraphQL API integration
- ✅ GitLab REST API integration (commits, forks, README/CONTRIBUTING sizes, closed issues)
- ✅ VCS abstraction layer (BaseVCSProvider, VCSRepositoryData)
- ✅ Data sampling in place (commits: 100, PRs: 50, forks: 20)
- ✅ VCSRepositoryData expanded (10 fields)
- ✅ MetricChecker base class and compatibility routing
- ✅ All metrics migrated to VCSRepositoryData
- ✅ GitLab issue close actors captured via closed issue data

### 問題点
- ❌ GitLab CI pipeline status is not wired yet (Build Health is skipped when unavailable)
- ❌ GitLab-specific metadata sources (security policy, license, code of conduct) remain limited
- ❌ GitLab score calibration still needs validation on real repositories

## 🏗️ アーキテクチャの問題

### 現在のデータフロー（問題あり）
```
GitLab API → VCSRepositoryData → _vcs_data_to_repo_info()
                                         ↓
                              GitHub形式の辞書（不完全）
                                         ↓
                              メトリクス関数（GitHub構造を期待）
                                         ❌ データが見つからない
```

### 理想的なデータフロー
```
任意のVCS → VCSRepositoryData → メトリクス関数（VCS非依存）
                                         ↓
                                    正確なスコア
```

## 📋 移行戦略

### 段階的アプローチの理由
- 25個のメトリクス関数を一度に変更するのはリスクが高い
- 既存のGitHub統合を破壊しない
- 各段階でテストと検証が可能
- ロールバックが容易

---

## Phase 1: 基盤整備 🔨

**期間**: 2-3週間 (40時間)  
**目標**: 新旧両方式をサポートする基盤を構築

### タスク

#### 1.1 VCSRepositoryDataの拡張 (8時間)

**ファイル**: `oss_sustain_guard/vcs/base.py`

不足しているフィールドを追加：

```python
class VCSRepositoryData(NamedTuple):
    # ... 既存フィールド ...
    
    # 新規追加
    star_count: int  # GitHubのstargazersCount, GitLabのstarCount
    description: str | None  # プロジェクトの説明
    homepage_url: str | None  # プロジェクトホームページ
    topics: list[str]  # リポジトリトピック/タグ
    readme_size: int | None  # READMEのサイズ（バイト）
    contributing_file_size: int | None  # CONTRIBUTING.mdのサイズ
    default_branch: str | None  # デフォルトブランチ名
    watchers_count: int  # ウォッチャー数
    open_issues_count: int  # オープンissue数
    language: str | None  # 主要プログラミング言語
```

#### 1.2 MetricCheckerベースクラスの作成 (8時間)

**ファイル**: `oss_sustain_guard/metrics/base.py`（新規作成）

```python
class MetricChecker(ABC):
    """VCS非依存のメトリクスチェッカー基底クラス"""
    
    @abstractmethod
    def check(self, vcs_data: VCSRepositoryData, context: MetricContext) -> Metric:
        """VCSRepositoryDataから直接チェック（新方式）"""
        pass
    
    def check_legacy(self, repo_info: dict[str, Any], context: MetricContext) -> Metric:
        """GitHub形式からチェック（後方互換性）
        
        デフォルト実装: repo_infoをVCSRepositoryDataに変換して新方式を呼ぶ
        """
        vcs_data = self._legacy_to_vcs_data(repo_info)
        return self.check(vcs_data, context)
    
    def _legacy_to_vcs_data(self, repo_info: dict[str, Any]) -> VCSRepositoryData:
        """GitHub形式の辞書をVCSRepositoryDataに変換"""
        # 実装...
```

#### 1.3 互換性レイヤーの構築 (16時間)

**ファイル**: `oss_sustain_guard/core.py`

`_analyze_repository_data()`を修正して、新旧両方式をサポート：

```python
def _analyze_repository_data(
    owner: str,
    name: str,
    repo_info: dict[str, Any],
    vcs_data: VCSRepositoryData | None = None,  # 新パラメータ
    platform: str | None = None,
    package_name: str | None = None,
    profile: str = "balanced",
) -> AnalysisResult:
    """新旧両方式をサポート"""
    
    for metric_spec in metric_specs:
        try:
            # 新方式をサポートしているか確認
            if vcs_data and hasattr(metric_spec.checker, 'check'):
                metric = metric_spec.checker.check(vcs_data, context)
            else:
                # 旧方式（後方互換性）
                metric = metric_spec.checker(repo_info, context)
            metrics.append(metric)
        except Exception as e:
            # エラーハンドリング...
```

#### 1.4 テスト基盤の整備 (8時間)

**ファイル**: `tests/metrics/test_base.py`（新規作成）

- VCSRepositoryDataのファクトリ関数
- モックデータ生成ヘルパー
- 新旧両方式のテストユーティリティ

### Phase 1 の成果物

- [x] VCSRepositoryDataに10個の新フィールド追加
- [x] MetricCheckerベースクラス実装
- [x] 互換性レイヤー実装
- [x] 互換性テスト追加（MetricChecker）
- [ ] 全既存テストがパス（部分テストのみ実行）

---

## Phase 2: コアメトリクスの移行 🚀

**期間**: 3-4週間 (56時間)  
**目標**: データ取得済みの重要メトリクスを優先的に移行

### 優先順位の高いメトリクス（7個）

これらはGitLabで既にデータ取得済み：

#### 2.1 Contributor Redundancy (6時間)

**ファイル**: `oss_sustain_guard/metrics/bus_factor.py`

**現在の問題**:
```python
# GitHub GraphQL構造に依存
default_branch = repo_info.get("defaultBranchRef")
commits_history = default_branch.get("target", {}).get("history", {}).get("edges", [])
```

**移行後**:
```python
class ContributorRedundancyChecker(MetricChecker):
    def check(self, vcs_data: VCSRepositoryData, context: MetricContext) -> Metric:
        commits = vcs_data.commits
        total_commits = vcs_data.total_commits
        # VCS非依存のロジック
```

**データ可用性**: ✅ commits配列（100件取得済み）

#### 2.2 Maintainer Retention (6時間)

**ファイル**: `oss_sustain_guard/metrics/maintainer_drain.py`

**データ可用性**: ✅ commits配列

#### 2.3 Recent Activity (6時間)

**ファイル**: `oss_sustain_guard/metrics/zombie_status.py`

**データ可用性**: ✅ pushed_at

#### 2.4 Change Request Resolution (6時間)

**ファイル**: `oss_sustain_guard/metrics/merge_velocity.py`

**データ可用性**: ✅ merged_prs配列（50件取得済み）

#### 2.5 Issue Resolution Duration (6時間)

**ファイル**: `oss_sustain_guard/metrics/issue_resolution_duration.py`

**データ可用性**: ✅ closed_issues配列（50件取得済み）

#### 2.6 Release Rhythm (6時間)

**ファイル**: `oss_sustain_guard/metrics/release_cadence.py`

**データ可用性**: ✅ releases配列（10件取得済み）

#### 2.7 Fork Activity (6時間)

**ファイル**: `oss_sustain_guard/metrics/fork_activity.py`

**データ可用性**: ✅ forks配列（20件取得済み）

### 各メトリクスの移行手順

1. **既存コードの分析** (1時間)
   - GitHubデータ構造への依存箇所を特定
   - 必要なVCSRepositoryDataフィールドを確認

2. **新方式の実装** (3時間)
   - MetricCheckerを継承
   - `check()`メソッドを実装
   - VCSRepositoryDataから直接データを取得

3. **テストの作成** (1.5時間)
   - GitHubデータでのテスト
   - GitLabデータでのテスト
   - エッジケースのテスト

4. **検証と調整** (0.5時間)
   - 既存テストの実行
   - スコアの一貫性確認

### Phase 2 の成果物

- [ ] 7個のコアメトリクスが新方式に移行
- [ ] GitLabリポジトリで正確なスコア算出
- [ ] 全テストがパス（GitHub/GitLab両方）
- [ ] スコアの後方互換性が保たれている

**期待される改善**:
- GitLabリポジトリのスコア: 32 → 60-70点に改善

---

## Phase 3: 残りのメトリクスの移行 📦

**期間**: 4-5週間 (108時間)  
**目標**: 全メトリクスをVCS非依存に

### 中優先度メトリクス（10個）

これらは追加データ取得が必要：

#### 3.1 データ拡張が必要なメトリクス

1. **Project Popularity** (5時間)
   - ファイル: `metrics/project_popularity.py`
   - 必要: `star_count`フィールド
   - GitLab: `starCount`から取得

2. **License Clarity** (4時間)
   - ファイル: `metrics/license_clarity.py`
   - 改善: `license_info`の形式統一

3. **Documentation Presence** (5時間)
   - ファイル: `metrics/community_health.py`
   - 必要: `readme_size`, `contributing_file_size`

4. **Contributor Attraction** (6時間)
   - ファイル: `metrics/attraction.py`
   - データ: commits配列（取得済み）

5. **Contributor Retention** (6時間)
   - ファイル: `metrics/retention.py`
   - データ: commits配列（取得済み）

6. **PR Acceptance Ratio** (5時間)
   - ファイル: `metrics/pr_acceptance_ratio.py`
   - データ: merged_prs, closed_prs（取得済み）

7. **PR Merge Speed** (5時間)
   - ファイル: `metrics/pr_merge_speed.py`
   - データ: merged_prs（取得済み）

8. **PR Responsiveness** (5時間)
   - ファイル: `metrics/pr_responsiveness.py`
   - データ: merged_prs（取得済み）

9. **Stale Issue Ratio** (5時間)
   - ファイル: `metrics/stale_issue_ratio.py`
   - データ: open_issues, closed_issues（取得済み）

10. **Organizational Diversity** (6時間)
    - ファイル: `metrics/organizational_diversity.py`
    - データ: commits配列（取得済み）

### 低優先度メトリクス（8個）

プラットフォーム依存性が高い：

11. **Security Signals** (8時間)
    - ファイル: `metrics/security.py`
    - GitLab: 異なるセキュリティモデル
    - 要調査: GitLab Security Dashboard API

12. **Build Health** (8時間)
    - ファイル: `metrics/build_health.py`
    - GitLab: CI/CD pipelines APIを使用

13. **Funding Signals** (4時間)
    - ファイル: `metrics/funding.py`
    - GitLab: 資金情報サポートなし

14. **Code of Conduct** (4時間)
    - ファイル: `metrics/code_of_conduct.py`
    - GitLab: ファイル検索API使用

15. **Single Maintainer Load** (5時間)
    - ファイル: `metrics/single_maintainer_load.py`
    - データ: commits, merged_prs（取得済み）

16. **Review Health** (5時間)
    - ファイル: `metrics/review_health.py`（未実装？）
    - GitLab: approvals API

17. **Dependents Count** (4時間)
    - ファイル: `metrics/dependents_count.py`
    - データ: Libraries.io（VCS非依存）

18. **Zombie Status** (4時間)
    - ファイル: `metrics/zombie_status.py`
    - データ: pushed_at（取得済み）

### Phase 3 の成果物

- [ ] 全25メトリクスが新方式に移行
- [ ] GitLabで完全なスコアリング
- [ ] プラットフォーム固有の機能差分を文書化
- [ ] 全テストがパス

**期待される改善**:
- GitLabリポジトリのスコア: 60-70 → 85-95点に改善（プロジェクトの実態に応じて）

---

## Phase 4: クリーンアップと最適化 🧹

**期間**: 1-2週間 (20時間)

### タスク

1. **旧方式の削除** (8時間)
   - `_vcs_data_to_repo_info()`の削減
   - GitHub形式変換ロジックの削除
   - レガシーコードのクリーンアップ

2. **パフォーマンス最適化** (6時間)
   - データ取得の効率化
   - キャッシュ戦略の見直し
   - 並列処理の改善

3. **ドキュメント更新** (6時間)
   - アーキテクチャドキュメント
   - 新規VCS追加ガイド
   - メトリクス実装ガイド

### Phase 4 の成果物

- [ ] 旧方式コードの完全削除
- [ ] パフォーマンス10-20%改善
- [ ] 完全なドキュメント

---

## 📁 影響を受けるファイル

### コア変更

```
oss_sustain_guard/
├── vcs/
│   ├── base.py                    ⚠️ VCSRepositoryData拡張
│   ├── github.py                  ⚠️ 新フィールド対応
│   └── gitlab.py                  ⚠️ 新フィールド対応
├── metrics/
│   ├── base.py                    🆕 新規作成
│   ├── bus_factor.py              ⚠️ リファクタリング
│   ├── maintainer_drain.py        ⚠️ リファクタリング
│   ├── zombie_status.py           ⚠️ リファクタリング
│   ├── merge_velocity.py          ⚠️ リファクタリング
│   ├── issue_resolution_duration.py ⚠️ リファクタリング
│   ├── release_cadence.py         ⚠️ リファクタリング
│   ├── fork_activity.py           ⚠️ リファクタリング
│   └── ... (残り18ファイル)       ⚠️ リファクタリング
└── core.py                        ⚠️ 互換性レイヤー追加
```

### テスト変更

```
tests/
├── metrics/
│   ├── test_base.py               🆕 新規作成
│   ├── test_bus_factor.py         ⚠️ 更新
│   ├── test_maintainer_drain.py   ⚠️ 更新
│   └── ... (全メトリクステスト)   ⚠️ 更新
└── vcs/
    ├── test_github.py             ⚠️ 更新
    └── test_gitlab.py             ⚠️ 更新
```

---

## ⏱️ タイムライン

### 全体スケジュール（約3-4ヶ月）

| Phase | 期間 | 工数 | 完了目標 |
|-------|------|------|---------|
| Phase 1: 基盤整備 | 2-3週間 | 40時間 | 2026年1月末 |
| Phase 2: コアメトリクス | 3-4週間 | 56時間 | 2026年2月末 |
| Phase 3: 残りメトリクス | 4-5週間 | 108時間 | 2026年3月末 |
| Phase 4: クリーンアップ | 1-2週間 | 20時間 | 2026年4月中旬 |
| **合計** | **約3.5ヶ月** | **224時間** | **2026年4月中旬** |

### マイルストーン

- ✅ **2026年1月2日**: GitLab Provider実装完了（データ取得）
- 🎯 **2026年1月31日**: Phase 1完了（基盤整備）
- 🎯 **2026年2月28日**: Phase 2完了（GitLabで60-70点）
- 🎯 **2026年3月31日**: Phase 3完了（GitLabで85-95点）
- 🎯 **2026年4月15日**: Phase 4完了（完全移行）

---

## 🎯 成功基準

### Phase 1
- [ ] 全既存テストがパス
- [ ] 互換性レイヤーが動作
- [ ] GitHubスコアに変化なし

### Phase 2
- [ ] GitLabリポジトリスコアが60点以上
- [ ] 7個のコアメトリクスで正確なスコア
- [ ] GitHub/GitLab両方でテスト通過

### Phase 3
- [ ] GitLabリポジトリスコアが85点以上（プロジェクトの実態に応じて）
- [ ] 全メトリクスで正確なスコア
- [ ] プラットフォーム差分が文書化

### Phase 4
- [ ] レガシーコードが削除
- [ ] パフォーマンス10%改善
- [ ] 完全なドキュメント

---

## ⚠️ リスクと対策

### リスク1: 既存機能の破壊

**影響度**: 🔴 高  
**対策**:
- 段階的移行（互換性レイヤー）
- 各Phase後に全テスト実行
- GitHubスコアの継続監視
- ロールバック計画の準備

### リスク2: スコア計算の不整合

**影響度**: 🟡 中  
**対策**:
- メトリクスごとに新旧比較
- 基準テストケースの作成
- スコア差分の文書化

### リスク3: プラットフォーム差異の未対応

**影響度**: 🟡 中  
**対策**:
- プラットフォーム固有機能の文書化
- 「データ利用不可」を明示的に処理
- プラットフォーム別のフォールバック戦略

### リスク4: スケジュール遅延

**影響度**: 🟢 低  
**対策**:
- 優先順位の明確化（Phase 2が最重要）
- 週次進捗確認
- Phase 3を分割可能に設計

---

## 📊 期待される効果

### 機能面
- ✅ GitLabで完全なスコアリング
- ✅ 将来的なVCS追加が容易（Bitbucket, Gitea, etc.）
- ✅ メトリクスのテスタビリティ向上
- ✅ コードの保守性向上

### 品質面
- ✅ プラットフォーム依存の削減
- ✅ データ構造の一貫性
- ✅ エラーハンドリングの改善

### 開発効率
- ✅ 新規メトリクス追加が容易
- ✅ モックテストが簡単
- ✅ デバッグが容易

---

## 🚀 開始方法

### 準備

1. **ブランチ作成**
   ```bash
   git checkout -b feature/vcs-metrics-migration
   ```

2. **Phase 1開始**
   ```bash
   # VCSRepositoryData拡張から開始
   vim oss_sustain_guard/vcs/base.py
   ```

3. **継続的テスト**
   ```bash
   # 各変更後にテスト実行
   make test
   ```

### レビューポイント

各Phaseの完了時に：
- [ ] コードレビュー
- [ ] テストカバレッジ確認（80%以上維持）
- [ ] パフォーマンステスト
- [ ] ドキュメント更新

---

## 📚 参考資料

- [VCS Abstraction Layer](./oss_sustain_guard/vcs/README.md)（作成予定）
- [Metric Implementation Guide](./docs/METRIC_IMPLEMENTATION.md)（作成予定）
- [GitLab API Documentation](https://docs.gitlab.com/ee/api/)
- [GitHub GraphQL API](https://docs.github.com/en/graphql)

---

## 🤝 コントリビューション

このプロジェクトは大規模なため、コミュニティの協力を歓迎します：

- **Phase 1-2**: コアチーム（互換性が重要）
- **Phase 3**: コミュニティ貢献可能（メトリクスごとに独立）
- **Phase 4**: コアチーム（最終調整）

---

**最終更新**: 2026年1月2日  
**ステータス**: Phase 1 完了 / Phase 2 準備中  
**次のマイルストーン**: Phase 2 コアメトリクス移行開始
