import unittest
from sprites.player import Player

class TestPlayer(unittest.TestCase):

    def setUp(self):
        # 每個測試函數執行前都會呼叫 setUp
        self.player = Player("TestPlayer")
    def test_initialization(self):
        self.assertEqual(self.player.name, "TestPlayer")
        self.assertEqual(self.player.score, 0)
        self.assertEqual(self.player.lives, 3) # 假設初始生命值為 3
    def test_add_score(self):
        self.player.add_score(100)
        self.assertEqual(self.player.score, 100)
        self.player.add_score(50)
        self.assertEqual(self.player.score, 150)
