"""Train toy model"""

from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
import numpy as np


def main():
    X, y = load_iris(return_X_y=True)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    clf = LogisticRegression(max_iter=1000).fit(Xtr, ytr)
    acc = clf.score(Xte, yte)
    np.savez("model.npz", coef_=clf.coef_, intercept_=clf.intercept_)
    print(f"Saved model.npz; test accuracy={acc:.3f}")


if __name__ == "__main__":
    main()
