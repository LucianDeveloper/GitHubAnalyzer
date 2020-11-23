import requests as r
from requests.models import Response
import sys
import argparse
from datetime import datetime
import re as regex
from typing import List, Union, Callable


def create_parser():
    """:return: Парсер параметров, указанных при запуске скрипта"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--url', default='https://github.com/aiogram/aiogram/')
    parser.add_argument('-s', '--start', default=None)
    parser.add_argument('-e', '--end', default=None)
    parser.add_argument('-b', '--branch', default='master')
    parser.add_argument('-t', '--token', default=None)
    return parser


class AnalyseException(Exception):
    """
    Класс для обработки исключений, связанных с работой скрипта
    """
    def __init__(self, text: str):
        self.text = text

    def __str__(self):
        return self.text


class GitHubAnalyzer:
    """Класс анализатора GitHub репозиториев"""

    API_URL = 'https://api.github.com/repos'
    BASE_LINE = '=' * 80

    def __init__(self, url: str,
                 start: datetime,
                 end: datetime,
                 branch: str,
                 token: Union[str, None]):
        """
        :param url: Адрес репозитория
        :param start: Дата начала анализа
        :param end: Дата конца анализа
        :param branch: Имя анализируемой ветки
        :param token: Токен доступа к github
        """
        self.user, self.rep = GitHubAnalyzer.get_params_by_url(url)
        self.base_url = f'{GitHubAnalyzer.API_URL}/{self.user}/{self.rep}'
        self.start: datetime = start
        self.end: datetime = end
        self.branch: str = branch

        self.session = r.Session()
        if token is not None:
            self.session.headers['Authorization'] = 'token %s' % token

        print(GitHubAnalyzer.BASE_LINE)
        print('| repo = %-20s user = %-20s branch = %-20s' % (self.rep, self.user, self.branch))
        print('| start date = %-14s end date = %-20s' % (
            self.start.strftime('%Y-%m-%d') if self.start is not None else None,
            self.end.strftime('%Y-%m-%d') if self.end is not None else None
        ))
        print(GitHubAnalyzer.BASE_LINE)

    @staticmethod
    def get_error_or_json(response: Response) -> List[dict]:
        """
        :param response: Ответ на GET запрос
        :return: Если ответ корректен, возвращает json обьект, иначе вызывает исключение
        """
        if response.status_code != 200:
            raise AnalyseException(
                f'При выполнении запроса {response.request} произошла ошибка.\n'
                f'Код ответа: {response.status_code}\n'
                f'\n'
                f'{response.json()}'
            )
        return response.json()

    def show_top_commits(self) -> None:
        """Вывод на экран 30 самых активных участников"""
        print(GitHubAnalyzer.BASE_LINE)
        print('%3s  %-30s | %3s' % ('N', 'Name', 'Count'))
        for index, item in enumerate(self.get_top_commits(), 1):
            print('%3d. %-30s | %3d' % (index, item['name'], item['count']))
        print(GitHubAnalyzer.BASE_LINE)

    def show_pr_info(self) -> None:
        """Вывод информации о Pull Requests на экран"""
        pulls = self.get_pull_requests()
        closed_pulls_n = len(list(filter(lambda pull: pull['state'] != 'open', pulls)))
        old_pulls_n = len(list(filter(
            lambda pull: (datetime.today() - pull['created_at']).days > 30 and pull['state'] == 'open', pulls
        )))
        self.print_info(len(pulls) - closed_pulls_n, closed_pulls_n, old_pulls_n, 'PR')

    @staticmethod
    def print_info(open_n: int, close_n: int, old_n: int, name: str) -> None:
        """
        :param open_n: Количество открытых элементов
        :param close_n: Количество закрытых элементов
        :param old_n: Количество устаревших элементов
        :param name: Название элементов
        """
        print(GitHubAnalyzer.BASE_LINE)
        print(f'| Open {name} = {open_n}\n'
              f'| Closed {name} = {close_n}\n'
              f'| Old {name} = {old_n}')
        print(GitHubAnalyzer.BASE_LINE)

    def get_issues_by_param(self, url: str, param: str):
        page = 1
        issues = []
        while True:
            tmp = GitHubAnalyzer.get_error_or_json(
                self.session.get(f'{url}state={param}&page={page}&per_page=1000'))
            if len(tmp) == 0:
                break
            issues += list(filter(
                lambda issue: GitHubAnalyzer.compare_dates(
                    self.end, GitHubAnalyzer.get_input_date_by_format(issue['created_at']),
                    lambda d1, d2: d1 > d2
                ), tmp
            ))
            page += 1
        return issues

    def show_issues_info(self) -> None:
        """Вывод информации о Issues на экран"""
        url = f'{self.base_url}/issues?'
        if self.start is not None:
            url += f'since={self.start.strftime("%Y-%m-%d")}&'
        close_issues = self.get_issues_by_param(url, 'closed')
        open_issues = self.get_issues_by_param(url, 'open')
        issues = open_issues + close_issues
        close_n = len(close_issues)
        old_pulls_n = len(list(filter(
            lambda issue: (datetime.today() - GitHubAnalyzer.get_input_date_by_format(issue['created_at'])).days > 14,
            open_issues
        )))
        self.print_info(len(issues) - close_n, close_n, old_pulls_n, 'Issues')

    @staticmethod
    def get_params_by_url(url: str) -> List[str]:
        """
        :param url: Адрес GitHub репозитория
        :return: Список из двух элементов - [user, repository]
        """
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
        """
        :param my_date: Дата начала или конца анализа, None если анализ не ограничен
        :param date: Какая то другая дата или None
        :param func: функция для сравнения дат
        :return: результат сравнения дат при помощи функции func
        """
        if my_date is None:
            return True
        if date is None:
            return False
        return func(my_date, date)

    def get_top_commits(self) -> List:
        """
        :return: Список 30 самых активных пользователей в порядке убывания
        """
        url = f'{self.base_url}/commits?per_page=1000'
        if self.branch is not None:
            url += f'&sha={self.branch}'
        commits = GitHubAnalyzer.get_error_or_json(self.session.get(url))
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
        authors = [f"{c['commit']['author']['name']}" for c in commits]
        return sorted(
            [{'name': author, 'count': authors.count(author)} for author in set(authors)],
            key=lambda x: -x['count']
        )[:30]

    def get_pull_requests(self) -> List:
        """
        :return: Список Pull Requests согласно настроек анализа
        """
        pulls = []
        page = 1
        while True:
            new_pulls = GitHubAnalyzer.get_error_or_json(
                self.session.get(f'{self.base_url}/pulls?page={page}&per_page=1000&state=all'))
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
        """
        :param date: Дата, указанная в строковом формате
        :return: Объект datetime или None, если дата указана неверно или не указана
        """
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
        branch=namespace.branch,
        token=namespace.token,
    )

    analyzer.show_top_commits()
    analyzer.show_pr_info()
    analyzer.show_issues_info()
