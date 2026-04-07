from typing import List, Optional, Dict, Any
from github import Github, GithubException
from .context_graph import CommitRecord
from . import config

class GitHubClient:
    def __init__(self):
        self.g = Github(config.GITHUB_TOKEN)

    def fetch_pr_data(self, pr_url: str) -> dict:
        """Parse URL and fetch PR metadata."""
        parts = pr_url.split('/')
        owner = parts[-4]
        repo_name = parts[-3]
        pr_number = int(parts[-1])

        repo = self.g.get_repo(f'{owner}/{repo_name}')
        pr = repo.get_pull(pr_number)
        files = list(pr.get_files())

        return {
            'pr_number': pr_number,
            'pr_title': pr.title,
            'pr_body': pr.body or '',
            'base_sha': pr.base.sha,
            'head_sha': pr.head.sha,
            'files': files,
            'repo': repo
        }

    def fetch_issue_data(self, issue_url: str) -> dict:
        """Parse URL and fetch Issue metadata."""
        parts = issue_url.split('/')
        owner = parts[-4]
        repo_name = parts[-3]
        issue_number = int(parts[-1])

        repo = self.g.get_repo(f'{owner}/{repo_name}')
        issue = repo.get_issue(issue_number)

        return {
            'issue_number': issue_number,
            'issue_title': issue.title,
            'issue_body': issue.body or '',
            'repo': repo
        }

    def fetch_full_file(self, repo, file_path: str, ref: str) -> Optional[str]:
        """Fetch complete file content at specific ref."""
        try:
            content = repo.get_contents(file_path, ref=ref)
            return content.decoded_content.decode('utf-8')
        except GithubException:
            return None  # New file added in PR

    def fetch_commit_history(self, repo, file_path: str, max_commits: int = 10) -> List[CommitRecord]:
        """Fetch commit history for a file."""
        try:
            commits = list(repo.get_commits(path=file_path))[:max_commits]
            records = []

            for commit in commits:
                msg = commit.commit.message.split('\n')[0]
                is_fix = any(kw in msg.lower() for kw in ['fix', 'regression', 'bug', 'revert'])

                records.append(CommitRecord(
                    sha=commit.sha[:8],
                    message=msg,
                    author=commit.commit.author.name,
                    date=commit.commit.author.date.isoformat(),
                    is_fix=is_fix,
                    changed_files=[f.filename for f in commit.files[:10]]
                ))

            return records
        except GithubException:
            return []

    def search_callers(self, repo, function_name: str, exclude_files: List[str]) -> List[str]:
        """Search for functions calling the given function using GitHub code search."""
        try:
            query = f'{function_name}( repo:{repo.full_name} language:Python'
            results = self.g.search_code(query)
            return [item.path for item in results[:10] if item.path not in exclude_files]
        except GithubException:
            return []
