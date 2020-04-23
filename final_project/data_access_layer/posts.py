from typing import List
from uuid import uuid4

from final_project.config import redis_settings
from final_project.data_access_layer.users import UsersDataAccessLayer
from final_project.exceptions import PostsDALError
from final_project.image_processor.worker import process_image
from final_project.messages import Message
from final_project.models import InPost, PostResponse
from final_project.redis_keys import RedisKey
from redis import Redis
from rq import Queue


class PostsDAL:
    @staticmethod
    async def add_post(user_id: int, post: InPost) -> PostResponse:
        user = await UsersDataAccessLayer.get_user(user_id, without_error=True)
        if not user:
            raise PostsDALError(Message.USER_DOES_NOT_EXISTS.value)
        ids = post.marked_users_ids
        if ids is not None and (
            not await PostsDAL._are_marked_users_correct(ids) or user_id in ids
        ):
            raise PostsDALError(Message.INCORRECTLY_MARKED_USERS.value)
        redis = Redis(redis_settings.redis_address)
        rq = Queue(connection=redis)
        rq.enqueue(process_image, user_id, post)
        task_id = str(uuid4())
        redis.sadd(RedisKey.TASKS_IN_PROGRESS, task_id)
        return PostResponse(
            status=Message.POST_ACCEPTED_FOR_PROCESSING.value, task_id=task_id
        )

    @staticmethod
    async def _are_marked_users_correct(marked_users_ids: List[int]) -> bool:
        s = set(marked_users_ids)
        if len(s) != len(marked_users_ids):
            return False
        return all(
            [
                await UsersDataAccessLayer.get_user(u_id, without_error=True)
                for u_id in marked_users_ids
            ]
        )
