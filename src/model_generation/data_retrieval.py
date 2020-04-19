from collections import Counter
from prawcore.exceptions import Forbidden, NotFound

import json
import praw
import progressbar as pg
import os


class DataRetriever(object):
    """
    Generate and format the data which is used to drive the model.
    """

    def __init__(self, worker_no=0, num_workers=1):
        """
        Load the config files and establish praw utility.
        :param worker_no: Int id of worker
        :param num_workers: Int number of workers, dictates division of labor between jobs.
        """
        print(os.listdir('.'))
        with open("model_generation/config.json", "r") as infile:  #
            self.config = json.loads(infile.read())
        if os.path.exists("model_generation/config_override.json"):
            with open("model_generation/config_override.json", "r") as infile:
                self.config.update(json.loads(infile.read()))

        self.reddit = praw.Reddit(user_agent="user", client_id=self.config["client_id"],
                                  client_secret=self.config["client_secret"])

        if worker_no >= num_workers:
            raise ValueError(f"worker_no passed {worker_no} >= the number of workers")

        self.i, self.total_instances = worker_no, num_workers
        self.usernames_path = self.config["usernames_path"].format(i=self.i)

    def get_random_usernames(self):
        """
        Get a random sample of usernames by randomly selecting subreddits and recent comments within that subreddit.
        :param number: Number of ids to retrieve
        :param ids_per_subreddit: Max number of ids per subreddit
        :param destination_file: The path of the text file to contain the exported ids.
        :return: None
        """
        ids = set()

        number = int(self.config["num_usernames"]/self.total_instances)
        max_ids_per_subreddit = 1000

        if self.i == 0:
            print("Getting random ids...")
            print(number)
            bar = pg.ProgressBar(max_value=number)
            bar.update(0)

        forbidden_count = 0

        while len(ids) < number:
            try:
                subreddit_name = self.reddit.subreddit("random").display_name
                subreddit = self.reddit.subreddit(subreddit_name)
                if subreddit.subscribers > 10000:  # For speed, ignore subreddits with very few subscribers as user origins.
                    old_id_num = len(ids)
                    for submission in subreddit.top(limit=10):
                        if len(submission.comments):
                            if submission.author:
                                ids.add((str(submission.author), subreddit_name))
                            for comment in submission.comments.list():
                                try:
                                    if comment.author:
                                        ids.add((str(comment.author), subreddit_name))
                                        if len(ids) - old_id_num > max_ids_per_subreddit:
                                            break
                                except AttributeError:
                                    pass
                    # For clarity, only display the status bar updates for the first worker.
                    if self.i == 0:
                        bar.update(min(number, len(ids)))
            except (Forbidden, NotFound):
                forbidden_count += 1
                if forbidden_count > 100:
                    print("Max exceptions exceeded, stopping remainder of auience selection")
                    break

        with open(self.usernames_path, "w") as outfile:
            outfile.write(json.dumps(list(ids)[:number]))

    def generate_user_subreddits_data(self):
        """
        Get a list of the distinct subreddits that the reddit accounts in a particular file have submitted or commented
        within.
        :param path_to_usernames: String path to the list of usernames.
        :param path_to_key_scores: Path to the output of ids to strings.
        :param path_to_decoder_json: Path to a JSON for decoding the strings.
        :return: None
        """
        try:
            with open(self.usernames_path, "r") as infile:
                usernames = json.loads(infile.read())
        except FileNotFoundError:
            usernames = {}  # Just pass so other threads can proceed normally.

        username_to_subreddit_scores = dict()
        if self.i == 0:  # For clarity, just show the status for one of the jobs.
            print("Getting subreddit visitation data...")
            work_range = pg.progressbar(usernames)
        else:
            work_range = usernames

        for username, origin_subreddit in work_range:
            subreddit_scores = self.get_distinct_subreddits_for_user(username, excluded_subreddit=origin_subreddit)
            if subreddit_scores:
                username_to_subreddit_scores[username] = subreddit_scores

        with open(self.config["subreddits_score_path"].format(i=self.i), "w") as outfile:
            outfile.write(json.dumps(username_to_subreddit_scores))

    def get_distinct_subreddits_for_user(self, username, excluded_subreddit=None):
        """
        Get a list of distinct subreddits a user has interacted with.
        :param username: String username of the user for which activity will be evaluated.
        :param excluded_subreddit: String name of subreddit to not be included in returned values or factor into counts.
        This value is normally used to prevent the subreddit from which a username was pulled from appearing in the output,
        which can skew the popularity metrics towards rarer randomly chosen subreddits.
        :return: Dict in format {
            String subreddit name: Float % of reddit interactions (submissions or comments) by a user which were in
                that subreddit.
        } on success, empty dict if API exception encountered
        """
        redditor = self.reddit.redditor(username)
        try:
            comment_subreddit_counts = Counter([str(comment.subreddit) for comment in redditor.comments.new(limit=300)])
            del comment_subreddit_counts[excluded_subreddit]
        except (Forbidden, NotFound):
            return {}

        try:
            submission_subreddit_counts = Counter([str(submission.subreddit) for submission in
                                                   redditor.submissions.new(limit=100)])
            del submission_subreddit_counts[excluded_subreddit]
        except (Forbidden, NotFound):
            return {}

        subreddits = set(comment_subreddit_counts.keys()).union(set(submission_subreddit_counts.keys()))
        total_actions = sum(comment_subreddit_counts.values()) + sum(submission_subreddit_counts.values())

        return {subreddit: (comment_subreddit_counts[subreddit] + submission_subreddit_counts[subreddit])/total_actions
            for subreddit in subreddits}

    def combine_and_prep_data(self, minimum_popularity=None, highest_num=64):
        """
        Taking the individual files produced in the generate subreddits for individual users step, combine them into:
            - For each user, a list of tuples of (Int, Float) with the Int being the popularity ranking of a subreddit
              and the Float what percentage of the user"s recent activity was in that subreddit. This file is saved
              to the value under key "combined_user_to_subreddit_score_path" in the config file.
            - Dump a JSON of {Integer Ranking: Subreddit name} for the subreddits visited by the users, where their
              popularity is above the minimum popularity ranking.
        :return: None
        """
        from collections import Counter

        if not minimum_popularity:
            minimum_popularity = self.config["max_subreddits_in_data"]

        combined_user_to_subreddit_scores = dict()
        subreddit_to_popularity = Counter()
        user_subreddit_score_directory = "/".join(self.config["subreddits_score_path"].split('/')[:-1])
        for file in os.listdir(user_subreddit_score_directory):
            path = os.path.join(user_subreddit_score_directory, file)
            if ".json" in file and int(file.split('.')[0].split('_')[-1]) < highest_num:
                with open(path, "r") as infile:
                    combined_user_to_subreddit_scores.update(json.loads(infile.read()))
        for subreddit_scores in combined_user_to_subreddit_scores.values():
            for subreddit, score in subreddit_scores.items():
                subreddit_to_popularity[subreddit] += score

        rank_to_subreddit = dict()
        for subreddit, _ in pg.progressbar(subreddit_to_popularity.most_common(minimum_popularity)):
            is_nsfw = True
            try:
                is_nsfw = False  # self.reddit.subreddit(subreddit).over18
            except Exception:
                print("Unable to get sfw status for subreddit " + subreddit)
                pass

            if not is_nsfw:
                rank_to_subreddit[len(rank_to_subreddit)+1] = subreddit

        with open(self.config["rank_to_subreddit_path"], "w") as outfile:
            outfile.write(json.dumps(rank_to_subreddit))

        subreddit_to_rank = {subreddit: rank for rank, subreddit in rank_to_subreddit.items()}

        output_data = {i:
            [(subreddit_to_rank[subreddit], score) for subreddit, score in user_subreddit_score.items() if subreddit
             in subreddit_to_rank] for i, user_subreddit_score in enumerate(combined_user_to_subreddit_scores.values())}
        with open(self.config["combined_user_to_subreddit_score_path"], "w") as outfile:
            outfile.write(json.dumps(output_data))


if __name__ == "__main__":
    import threading
    import os

    os.chdir('..')

    def get_data_slice(i, j):
        data_retriever = DataRetriever(worker_no=i, num_workers=j)
        # data_retriever.get_random_usernames()
        data_retriever.generate_user_subreddits_data()

    max_threads = 64
    jobs = []
    print(f"Starting work on {max_threads} jobs.")
    for i in range(max_threads):
        p = threading.Thread(target=get_data_slice, args=(i, max_threads))
        jobs.append(p)
        p.start()

    for j in jobs:
        j.join()

    data_retriever = DataRetriever(worker_no=0, num_workers=1)
    data_retriever.combine_and_prep_data(highest_num=max_threads)

