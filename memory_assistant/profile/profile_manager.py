"""
用户画像管理器
管理用户画像的CRUD操作
"""
import json
import os
from typing import Optional, Dict, Any
from datetime import datetime

from ..models.user_profile import UserProfile


class ProfileManager:
    """用户画像管理器"""

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        self.profiles: Dict[str, UserProfile] = {}
        self._ensure_dir()

    def _ensure_dir(self):
        """确保数据目录存在"""
        os.makedirs(self.data_dir, exist_ok=True)

    def _get_profile_path(self, user_id: str) -> str:
        """获取用户画像文件路径"""
        return os.path.join(self.data_dir, f"{user_id}_profile.json")

    async def get_profile(self, user_id: str) -> UserProfile:
        """
        获取用户画像（如果不存在则创建）

        Args:
            user_id: 用户ID

        Returns:
            用户画像
        """
        profile_path = self._get_profile_path(user_id)
        if os.path.exists(profile_path):
            try:
                with open(profile_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                profile = UserProfile.from_dict(data)
            except Exception as e:
                print(f"Error loading profile for {user_id}: {e}")
                profile = self.profiles.get(user_id, UserProfile(user_id=user_id))
        elif user_id in self.profiles:
            # 文件不存在时再回退到内存缓存
            profile = self.profiles[user_id]
        else:
            # 创建新画像
            profile = UserProfile(user_id=user_id)

        # 缓存到内存
        self.profiles[user_id] = profile
        return profile

    async def save_profile(self, profile: UserProfile) -> bool:
        """
        保存用户画像

        Args:
            profile: 用户画像

        Returns:
            是否成功
        """
        try:
            profile.updated_at = datetime.now()

            # 更新内存缓存
            self.profiles[profile.user_id] = profile

            # 保存到文件
            profile_path = self._get_profile_path(profile.user_id)
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            print(f"Error saving profile: {e}")
            return False

    async def update_profile(self, user_id: str,
                            updates: Dict[str, Any]) -> Optional[UserProfile]:
        """
        更新用户画像

        Args:
            user_id: 用户ID
            updates: 更新内容

        Returns:
            更新后的画像
        """
        profile = await self.get_profile(user_id)

        # 应用更新
        if 'interaction_style' in updates:
            style = updates['interaction_style']
            for key, value in style.items():
                if hasattr(profile.interaction_style, key):
                    setattr(profile.interaction_style, key, value)

        if 'expertise_areas' in updates:
            profile.expertise_areas = updates['expertise_areas']

        # 保存更新
        await self.save_profile(profile)
        return profile

    async def delete_profile(self, user_id: str) -> bool:
        """
        删除用户画像

        Args:
            user_id: 用户ID

        Returns:
            是否成功
        """
        try:
            # 从内存移除
            if user_id in self.profiles:
                del self.profiles[user_id]

            # 删除文件
            profile_path = self._get_profile_path(user_id)
            if os.path.exists(profile_path):
                os.remove(profile_path)

            return True
        except Exception as e:
            print(f"Error deleting profile: {e}")
            return False

    async def get_profile_stats(self, user_id: str) -> Dict[str, Any]:
        """
        获取画像统计信息

        Args:
            user_id: 用户ID

        Returns:
            统计信息
        """
        # 统计接口优先从磁盘重新加载，避免外部写入后读到陈旧缓存
        profile = await self.get_profile(user_id)

        if not profile:
            return {}

        return {
            'user_id': user_id,
            'created_at': profile.created_at.isoformat(),
            'updated_at': profile.updated_at.isoformat(),
            'topic_count': len(profile.topic_preferences),
            'top_topics': [
                {'topic': p.topic, 'weight': p.weight}
                for p in sorted(profile.topic_preferences,
                               key=lambda x: x.weight, reverse=True)[:5]
            ],
            'expertise_count': len(profile.expertise_areas),
            'expertise_areas': [
                {'domain': e.domain, 'level': e.level, 'confirmed': e.confirmed}
                for e in profile.expertise_areas
            ],
            'interaction_style': {
                'preferred_response_length': profile.interaction_style.preferred_response_length,
                'preferred_formality': profile.interaction_style.preferred_formality,
                'preferred_detail_level': profile.interaction_style.preferred_detail_level,
                'proactivity_level': profile.interaction_style.proactivity_level,
                'expressiveness': profile.interaction_style.expressiveness,
            },
            'total_interactions': profile.behavior_stats.total_interactions,
        }
