# core/leaderboard_manager.py

import json
import os
import datetime
import settings

class LeaderboardManager:
    def __init__(self):
        self.leaderboard_file = settings.LEADERBOARD_FILE
        self.max_entries = settings.LEADERBOARD_MAX_ENTRIES
        self.scores = self.load_scores()

    def load_scores(self):
        """從 JSON 檔案載入排行榜數據。"""
        if not os.path.exists(self.leaderboard_file):
            # 如果檔案不存在，返回一個空的列表，並在之後儲存時創建檔案
            return []
        try:
            with open(self.leaderboard_file, 'r', encoding='utf-8') as f:
                scores = json.load(f)
            # 確保分數是按降序排列的
            scores.sort(key=lambda x: x.get('score', 0), reverse=True)
            return scores
        except (json.JSONDecodeError, FileNotFoundError, TypeError):
            # 如果檔案損壞或為空，也返回空列表
            return []

    def save_scores(self):
        """將排行榜數據儲存到 JSON 檔案。"""
        try:
            # 確保 data 目錄存在
            os.makedirs(os.path.dirname(self.leaderboard_file), exist_ok=True)
            with open(self.leaderboard_file, 'w', encoding='utf-8') as f:
                json.dump(self.scores, f, ensure_ascii=False, indent=4)
        except IOError as e:
            print(f"錯誤：無法儲存排行榜檔案 '{self.leaderboard_file}': {e}")

    def add_score(self, player_name, score, ai_defeated_type):
        """
        新增一個分數到排行榜。
        如果分數夠高，則加入並保持排行榜長度和排序。
        """
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        new_entry = {
            "name": player_name,
            "score": score,
            "ai_defeated": ai_defeated_type,
            "date": current_time
        }

        self.scores.append(new_entry)
        # 按分數降序排列
        self.scores.sort(key=lambda x: x.get('score', 0), reverse=True)
        # 只保留前 N 名
        self.scores = self.scores[:self.max_entries]
        
        # 檢查新分數是否真的進入了排行榜（即是否在前 N 名內）
        # 這一檢查是為了確定是否需要儲存檔案
        # 一個簡單的方法是比較加入前後的列表，但由於我們總是排序和截斷，
        # 只要列表長度小於 max_entries，或者新分數高於列表最後一個分數，就意味著有變化
        
        # 為了簡化，我們可以在每次嘗試新增後都儲存
        self.save_scores()
        print(f"新增分數：{player_name}, {score}, AI: {ai_defeated_type}。目前排行榜長度：{len(self.scores)}")

    def get_scores(self):
        """返回排行榜列表。"""
        return self.scores

    def is_score_high_enough(self, score):
        """檢查一個分數是否夠高，可以進入排行榜。"""
        if len(self.scores) < self.max_entries:
            return True # 如果排行榜還沒滿，任何分數都可以進入
        # 如果排行榜已滿，新分數必須高於榜上最低分
        return score > self.scores[-1].get('score', 0)