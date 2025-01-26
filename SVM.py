import numpy as np
from numpy import array
import matplotlib.pyplot as plt
from sklearn.svm import SVC
from sklearn.preprocessing import normalize
from sklearn.metrics import ConfusionMatrixDisplay
from sklearn.metrics import precision_recall_fscore_support

num_votes = 12

results = []


for vote_id in range(num_votes):
    print("VOTE = ", vote_id)

    # train label
    train_y = []
    read_label = open("features/train_label.txt", "r")
    train_y = read_label.readlines()
    train_y = [int(i) for i in train_y]
    train_y = array(train_y)

    # test label
    y = []
    read_label = open("features/label.txt", "r")
    y = read_label.readlines()
    y = [int(i) for i in y]
    y = array(y)

    # train featrue
    train_X = []
    read_feature = open("features/train_feature_"+str(vote_id)+".txt", "r")
    lines = read_feature.readlines()
    for line in lines:
        line = line.split('\n')[0]
        line = line.split(' ')
        # print(line)
        line = [float(i) for i in line]
        train_X.append(line)
    train_X = array(train_X)

    # test featrue
    X = []
    read_feature = open("features/feature_"+str(vote_id)+".txt", "r")
    lines = read_feature.readlines()
    for line in lines:
        line = line.split('\n')[0]
        line = line.split(' ')
        line = [float(i) for i in line]
        X.append(line)
    X = array(X)

    # pick percentage of random points
    # percentage = 100
    # count = len(train_X) // percentage
    # choice = np.random.randint(len(train_X), size=count)
    # train_X = train_X[choice, :]
    # train_y = train_y[choice]


    clf = SVC(gamma='auto')
    clf.fit(train_X, train_y)

    SVC(C=1.0, cache_size=200, class_weight=None, coef0=0.0,
        decision_function_shape='ovr', degree=3, gamma='auto', kernel='rbf',
        max_iter=-1, probability=False, random_state=None, shrinking=True,
        tol=0.001, verbose=False)

    results.append(clf.score(X, y))
    print(clf.score(X, y))
    titles_options = [
        ("Confusion matrix, without normalization", None),
    ]
    for title in titles_options:
        disp = ConfusionMatrixDisplay.from_estimator(
            clf,
            X,
            y,
        )
        disp.ax_.set_title(title)

        print(title)
        print(disp.confusion_matrix)
        plt.show()

    y_pred = clf.predict(X)
    print(precision_recall_fscore_support(y, y_pred))
results = array(results)
print('mean', np.mean(results))
