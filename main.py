import requests as r
from requests.models import Response
import sys
import argparse
from datetime import datetime
import re as regex
from typing import List, Union, Callable


def create_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--url', default='https://github.com/aiogram/aiogram/')
    parser.add_argument('-s', '--start', default=None)
    parser.add_argument('-e', '--end', default='2020-11-09')
    parser.add_argument('-b', '--branch', default='dev-2.x')
    return parser


class AnalyseException(Exception):
    def __init__(self, text: str):
        self.text = text

    def __str__(self):
        return self.text

    @staticmethod
    def get_error_or_json(response: Response) -> List[dict]:
        if response.status_code != 200:
            raise AnalyseException(
                f'При выполнении запроса {response.request} произошла ошибка.\n'
                f'Код ответа: {response.status_code}\n'
                f'\n'
                f'{response.json()}'
            )
        return response.json()


class GitHubAnalyzer:
    API_URL = 'https://api.github.com/repos'
    BASE_LINE = '=' * 80

    def __init__(self, url: str, start: datetime, end: datetime, branch: str):
        self.user, self.rep = GitHubAnalyzer.get_params_by_url(url)
        self.base_url = f'{GitHubAnalyzer.API_URL}/{self.user}/{self.rep}'
        self.start: datetime = start
        self.end: datetime = end
        self.branch: str = branch

        print(GitHubAnalyzer.BASE_LINE)
        print('| repo = %-20s user = %-20s branch = %-20s' % (self.rep, self.user, self.branch))
        print('| start date = %-14s end date = %-20s' % (
            self.start.strftime('%Y-%m-%d') if self.start is not None else None,
            self.end.strftime('%Y-%m-%d') if self.end is not None else None
        ))
        print(GitHubAnalyzer.BASE_LINE)

    def show_top_comments(self) -> None:
        print(GitHubAnalyzer.BASE_LINE)
        print('%s  %-30s | %3s' % ('N', 'Name', 'Count'))
        for index, item in enumerate(self.get_top_commits(), 1):
            print('%d. %-30s | %3d' % (index, item['name'], item['count']))
        print(GitHubAnalyzer.BASE_LINE)

    def show_pr_info(self) -> None:
        pulls = self.get_pull_requests()
        closed_pulls_n = len(list(filter(lambda pull: pull['state'] != 'open', pulls)))
        old_pulls_n = len(list(filter(
            lambda pull: (datetime.today() - pull['created_at']).days > 30 and pull['state'] == 'open', pulls
        )))
        self.print_info(len(pulls) - closed_pulls_n, closed_pulls_n, old_pulls_n, 'PR')

    @staticmethod
    def print_info(open_n: int, close_n: int, old_n: int, name: str):
        print(GitHubAnalyzer.BASE_LINE)
        print(f'| Open {name} = {open_n}\n'
              f'| Closed {name} = {close_n}\n'
              f'| Old {name} = {old_n}')
        print(GitHubAnalyzer.BASE_LINE)

    def show_issues_info(self):
        url = f'{self.base_url}/issues?'
        if self.start is not None:
            url += f'since={self.start.strftime("%Y-%m-%d")}&'
        open_issues = AnalyseException.get_error_or_json(r.get(f'{url}state=open'))
        close_issues = AnalyseException.get_error_or_json(r.get(f'{url}state=closed'))
        issues = open_issues + close_issues
        close_n = len(close_issues)
        old_pulls_n = len(list(filter(
            lambda issue: (datetime.today() - GitHubAnalyzer.get_input_date_by_format(issue['created_at'])).days > 14,
            open_issues
        )))
        self.print_info(len(issues) - close_n, close_n, old_pulls_n, 'Issues')

    @staticmethod
    def get_params_by_url(url: str) -> List[str]:
        params = url.replace('github.com/', '').replace('https://', '').split('/')[:2]
        if len(params) != 2:
            raise AnalyseException(
                f'При обработке адреса {url} произошла ошибка. Невозможно '
                f'извлечь имя пользователя и название репозитория')
        return params

    @staticmethod
    def compare_dates(
            my_date: Union[datetime, None],
            date: Union[datetime, None],
            func: Callable[[datetime, datetime], bool]
    ) -> bool:
        if my_date is None:
            return True
        if date is None:
            return False
        return func(my_date, date)

    def get_top_commits(self) -> List:
        url = f'{self.base_url}/commits'
        if self.branch is not None:
            url += f'?sha={self.branch}'
        commits = AnalyseException.get_error_or_json(r.get(url))
        commits = list(filter(
            lambda item: GitHubAnalyzer.compare_dates(
                self.start, GitHubAnalyzer.get_input_date_by_format(item['commit']['committer']['date']),
                lambda d1, d2: d1 < d2
            ) and GitHubAnalyzer.compare_dates(
                self.end, GitHubAnalyzer.get_input_date_by_format(item['commit']['committer']['date']),
                lambda d1, d2: d1 > d2
            ),
            commits
        ))
        authors = [f"{c['commit']['author']['name']} ({c['committer']['login']})" for c in commits]
        return sorted(
            [{'name': author, 'count': authors.count(author)} for author in set(authors)],
            key=lambda x: -x['count']
        )[:30]

    def get_pull_requests(self) -> List:
        pulls = []
        page = 1
        while True:
            new_pulls = AnalyseException.get_error_or_json(r.get(f'{self.base_url}/pulls?page={page}'))
            if len(new_pulls) == 0:
                break
            new_pulls = list(filter(
                lambda item: GitHubAnalyzer.compare_dates(
                    self.start, GitHubAnalyzer.get_input_date_by_format(item['created_at']),
                    lambda d1, d2: d1 < d2
                ) and GitHubAnalyzer.compare_dates(
                    self.end, GitHubAnalyzer.get_input_date_by_format(item['created_at']),
                    lambda d1, d2: d1 > d2
                ),
                new_pulls
            ))
            for pull in new_pulls:
                if self.branch is not None and pull['base']['ref'] != self.branch:
                    continue
                pulls.append({
                    'number': pull['number'],
                    'created_at': GitHubAnalyzer.get_input_date_by_format(pull['created_at']),
                    'closed_at': GitHubAnalyzer.get_input_date_by_format(pull['closed_at']),
                    'state': pull['state'],
                })
            page += 1
        return pulls

    @staticmethod
    def get_input_date_by_format(date: str) -> Union[datetime, None]:
        if date is None:
            return None
        x = regex.search(
            r'(19|20)\d\d-((0[1-9]|1[012])-(0[1-9]|[12]\d)|(0[13-9]|1[012])-30|(0[13578]|1[02])-31)', date
        )
        return datetime.strptime(x.group(0), '%Y-%m-%d') if x is not None else None


if __name__ == '__main__':
    namespace = create_parser().parse_args(sys.argv[1:])

    s_date = GitHubAnalyzer.get_input_date_by_format(namespace.start)
    e_date = GitHubAnalyzer.get_input_date_by_format(namespace.end)

    analyzer = GitHubAnalyzer(
        url=namespace.url,
        start=s_date,
        end=e_date,
        branch=namespace.branch
    )

    analyzer.show_top_comments()
    analyzer.show_pr_info()
    analyzer.show_issues_info()
