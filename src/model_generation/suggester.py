from .data_retrieval import DataRetriever
from .modeling import SuggestionModeler
import json


class Suggester(object):

    def __init__(self):
        self.retriever = DataRetriever()
        self.model = SuggestionModeler()

    def get_estimates_for_user(self, username):
        """
        Given a username, generate a list of suggested subreddits they may enjoy based on their recent activity.
        :param username: String username
        :return: String dumped json in format {
            'success': True or False,
            'message: None or description of error,
            'data': List of 200 subreddits ranked by confidence, values
               [String subreddit name, float confidence, int popularity rating]
        }
        """
        username = username.strip()
        user_data = self.retriever.get_distinct_subreddits_for_user(username)
        if not user_data:
            return json.dumps({
                'success': True,
                'message': 'No reddit data found for user ' + username
            })
        res = self.model.get_user_predictions(user_data)[:200]
        return json.dumps({
            'success': True,
            'data': res
        })
