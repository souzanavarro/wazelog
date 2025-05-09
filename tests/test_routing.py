import unittest
import numpy as np
import pandas as pd
from routing import pos_processamento, utils

class TestPosProcessamento(unittest.TestCase):
    def setUp(self):
        self.dist_matrix = np.array([
            [0, 10, 15, 20],
            [10, 0, 35, 25],
            [15, 35, 0, 30],
            [20, 25, 30, 0]
        ])
        self.rota = [0, 1, 2, 3, 0]

    def test_2opt(self):
        rota_otimizada = pos_processamento.heuristica_2opt(self.rota, self.dist_matrix)
        self.assertIsInstance(rota_otimizada, list)
        self.assertEqual(rota_otimizada[0], 0)
        self.assertEqual(rota_otimizada[-1], 0)

    def test_split(self):
        sub_rotas = pos_processamento.split(self.rota, max_paradas_por_subrota=2)
        self.assertTrue(all(r[0] == 0 and r[-1] == 0 for r in sub_rotas))

    def test_merge(self):
        rotas = [[0, 1, 0], [0, 2, 3, 0]]
        demandas = [0, 5, 8, 3]
        rotas_merged = pos_processamento.merge(rotas, self.dist_matrix, capacidade_maxima=20, demandas=demandas)
        self.assertTrue(isinstance(rotas_merged, list))

class TestUtils(unittest.TestCase):
    def test_validar_dataframe(self):
        df = pd.DataFrame({'A': [1], 'B': [2]})
        ok, msg = utils.validar_dataframe(df, ['A', 'B'])
        self.assertTrue(ok)
        ok, msg = utils.validar_dataframe(df, ['A', 'C'])
        self.assertFalse(ok)

    def test_validar_matriz(self):
        mat = np.eye(3)
        ok, msg = utils.validar_matriz(mat, tamanho_esperado=3)
        self.assertTrue(ok)
        ok, msg = utils.validar_matriz(mat, tamanho_esperado=4)
        self.assertFalse(ok)

if __name__ == '__main__':
    unittest.main()
