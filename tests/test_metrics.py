import unittest
from app import as_num, excel_date, build_data

class MetricsTest(unittest.TestCase):
    def test_invalid_numbers_are_not_zero(self):
        for value in ('', None, '#DIV/0!', 'NaN', 'Infinity', True):
            self.assertIsNone(as_num(value))
        self.assertEqual(as_num('R$ 1.234,56'), 1234.56)
        self.assertEqual(as_num(0), 0)

    def test_dates(self):
        self.assertEqual(excel_date('15/02/2026'), '2026-02-15')
        self.assertIsNone(excel_date('2026-02-31'))

    def test_records_missing_fields_and_zero(self):
        rows = [[None, 'CLIENTE'] + [None]*11,
                ['01/01/2026', 'Cliente A', 'SAO PAULO', None, '', 0, '#VALUE!', None, None, None, None, 10, 'SIM'],
                [None]*13,
                [None, 'Cliente B']]
        result = build_data(rows, 'Teste', 'fixture', '2026-01-01T00:00:00Z')
        self.assertEqual(len(result['records']), 2)
        self.assertEqual(result['meta']['linhasDescartadas'], 1)
        first = result['records'][0]
        self.assertEqual(first['filial'], 'SÃO PAULO')
        self.assertEqual(first['gasto'], 0)
        self.assertIsNone(first['target'])
        self.assertIsNone(first['economia'])
        self.assertIsNone(first['diasUteis'])
        self.assertIsNone(result['records'][1]['efetivo'])

if __name__ == '__main__':
    unittest.main()
