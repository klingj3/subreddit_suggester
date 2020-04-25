import json
import numpy as np
import os

from keras.models import Sequential
from keras.layers import Dense, Dropout, Embedding, Flatten, Activation, BatchNormalization
from sklearn.model_selection import train_test_split


class SuggestionModeler(object):
    """
    A collection of functions to generate a model of subreddit suggestions from the data retreived in
    data_retrieval.py
    """
    def __init__(self, force_retrain=False):
        with open("model_generation/config.json", "r") as infile:
            self.config = json.loads(infile.read())
        if os.path.exists("config_override.json"):
            with open("model_generation/config_override.json", "r") as infile:
                self.config.update(json.loads(infile.read()))

        self.subreddit_to_rank = dict()
        with open(self.config["rank_to_subreddit_path"], 'r') as infile:
            self.rank_to_subreddit = json.loads(infile.read())
            self.rank_to_subreddit = {int(k): v for k, v in self.rank_to_subreddit.items()}
            for rank, subreddit in self.rank_to_subreddit.items():
                self.subreddit_to_rank[subreddit] = rank
        with open(self.config['rank_to_sfw_status'], 'r') as infile:
            self.rank_to_sfw_status = json.loads(infile.read())
            self.rank_to_sfw_status = {int(k): v for k, v in self.rank_to_sfw_status.items()}

        self.method = self.config["method"]
        self.model_path = self.config['model_path'].format(method=self.method)

        if self.method == "embedding":
            model = Sequential()
            model.add(Embedding(self.config['max_subreddits_in_model']+1, 256,
                                input_length=self.config['max_subreddits_per_user_vector']))
            model.add(Flatten())
            model.add(Dense(256, activation='relu'))
            model.add(Dense(self.config['max_subreddits_in_model'], activation='sigmoid'))
            model.compile(loss='binary_crossentropy', optimizer='rmsprop', metrics=['acc'])
        elif self.method == "hot":
            model = Sequential()
            model.add(Dense(512, activation='relu',
                            input_shape=(self.config['max_subreddits_in_model'], )))
            model.add(Dropout(0.5))
            model.add(Dense(self.config['max_subreddits_in_model'], activation='sigmoid'))
            model.compile(loss='binary_crossentropy', optimizer='rmsprop', metrics=['acc'])
        else:
            raise ValueError("'method' in config not well defined")

        self.model = model
        if force_retrain or not os.path.exists(self.model_path):
            model.summary()
            print("Preparing train/test data...")
            X, y = self.arrange_training_data(method=self.method)
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=self.config['test_pct'])

            train_data, test_data = (X_train, y_train), (X_test, y_test)
            print("Starting training process...")
            self.train_model(train_data, test_data)
        self.model.load_weights(self.model_path)

    def arrange_training_data(self, method):
        import random

        with open(self.config["combined_user_to_subreddit_score_path"], 'r') as infile:
            user_subreddit_scores = json.loads(infile.read())

        for k, scores in user_subreddit_scores.items():
            user_subreddit_scores[k] = sorted(scores, key=lambda x: x[1], reverse=True)

        data_length, data_width = len(user_subreddit_scores), self.config['max_subreddits_in_model']
        user_subreddit_scores = list(user_subreddit_scores.values())
        random.shuffle(user_subreddit_scores)

        if method == 'embedding':  # Used for input to Embedding layer
            X = np.zeros((data_length, self.config['max_subreddits_per_user_vector']), dtype=np.uint16)
            for i, scores in enumerate(user_subreddit_scores):
                for j, subreddit_key in enumerate(x for x, _ in scores[:self.config['max_subreddits_per_user_vector']]
                                                  if x < self.config['max_subreddits_in_model']):
                    X[i][j] = subreddit_key
        elif method == 'hot':  # Input vector is one-hot encoding.
            X = np.zeros((data_length, data_width), dtype=np.bool)
            for i, scores in enumerate(user_subreddit_scores):
                for subreddit_key, score in scores:
                    if subreddit_key <= data_width:
                        X[i][subreddit_key - 1] = True
        else:
            raise ValueError(f"Unhandled training data preparation method {method}")


        y = np.zeros((data_length, data_width), dtype=np.bool)
        for i, scores in enumerate(user_subreddit_scores):
            for subreddit_key, score in scores:
                if subreddit_key <= data_width:
                    y[i][subreddit_key-1] = score > 0
        return X, y

    def arrange_user_data(self, user_data):
        user_data = {k: v for k, v in sorted(user_data.items(), key=lambda x: x[1], reverse=True)
                     if 0 < self.subreddit_to_rank.get(k, -1) < self.config['max_subreddits_in_model']}
        if self.method == 'embedding':
            data = np.zeros((1, self.config['max_subreddits_per_user_vector']), dtype=np.uint16)
            for i, subreddit_name in enumerate(list(user_data.keys())[:self.config['max_subreddits_per_user_vector']]):
                data[0][i] = self.subreddit_to_rank[subreddit_name]
        if self.method == 'hot':
            data = np.zeros((1, self.config['max_subreddits_in_model']), dtype=np.bool)
            for subreddit_name, subreddit_score in user_data.items():
                if subreddit_name in self.subreddit_to_rank:
                    data[0][self.subreddit_to_rank[subreddit_name]-1] = subreddit_score > 0

        return data

    def train_model(self, train_data, test_data):
        X, y = train_data
        self.model.fit(X, y, epochs=5, batch_size=256, verbose=1)
        self.model.save(self.model_path)
        X, y = test_data
        scores = self.model.evaluate(X, y, verbose=1)
        print(self.model.metrics_names)
        print(scores)

    def get_user_predictions(self, user_data):
        import math
        arranged_data = self.arrange_user_data(user_data)
        user_known_subreddits = set(list(user_data.keys()))
        predictions = self.model.predict(arranged_data)[0]
        predictions = [(self.rank_to_subreddit[i+1], round(float(score), 5), i) for i, score
                       in enumerate(predictions) if self.rank_to_subreddit[i+1] not in user_known_subreddits \
                       and self.rank_to_sfw_status[i+1] and i > 200]
        predictions.sort(key=lambda x: x[1], reverse=True)
        return predictions


if __name__ == '__main__':
    import os
    os.chdir('..')
    modeler = SuggestionModeler(True)

