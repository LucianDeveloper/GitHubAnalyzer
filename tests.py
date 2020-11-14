import unittest
from datetime import datetime

from main import GitHubAnalyzer, AnalyseException


class TestDate(unittest.TestCase):
    def test_correct_date(self):
        self.assertEqual(GitHubAnalyzer.get_input_date_by_format('2020-10-10'), datetime(year=2020, month=10, day=10))

    def test_wrong_date(self):
        self.assertEqual(GitHubAnalyzer.get_input_date_by_format('1234-10-10'), None)
        self.assertEqual(GitHubAnalyzer.get_input_date_by_format('2020-77-10'), None)
        self.assertEqual(GitHubAnalyzer.get_input_date_by_format('2020-10-77'), None)

    @unittest.expectedFailure
    def test_fail(self):
        self.assertRaises(
            AnalyseException,
            GitHubAnalyzer.get_input_date_by_format(1234578)
        )

    def test_date_compare(self):
        date_1 = datetime(year=2020, month=10, day=10)
        date_2 = datetime(year=2019, month=10, day=10)
        self.assertFalse(GitHubAnalyzer.compare_dates(date_1, date_2, lambda d1, d2: d1 < d2))
        self.assertFalse(GitHubAnalyzer.compare_dates(date_1, None, lambda d1, d2: d1 < d2))
        self.assertTrue(GitHubAnalyzer.compare_dates(None, date_2, lambda d1, d2: d1 < d2))
        self.assertTrue(GitHubAnalyzer.compare_dates(None, None, lambda d1, d2: d1 < d2))


class TestUrlParams(unittest.TestCase):
    def test_params_correct(self):
        self.assertEqual(
            GitHubAnalyzer.get_params_by_url('https://github.com/LucianDeveloper/GitHubAnalyzer'),
            ['LucianDeveloper', 'GitHubAnalyzer']
        )
        self.assertEqual(
            GitHubAnalyzer.get_params_by_url('github.com/LucianDeveloper/GitHubAnalyzer'),
            ['LucianDeveloper', 'GitHubAnalyzer']
        )

        self.assertEqual(
            GitHubAnalyzer.get_params_by_url('LucianDeveloper/GitHubAnalyzer'),
            ['LucianDeveloper', 'GitHubAnalyzer']
        )

    @unittest.expectedFailure
    def test_fail(self):
        self.assertRaises(
            AnalyseException,
            GitHubAnalyzer.get_params_by_url('LucianDeveloper GitHubAnalyzer')
        )


if __name__ == '__main__':
    unittest.main()
