# Plotting tools implementation
import matplotlib.pyplot as plt


def plot_bar(df, x, y):
    df.plot(kind="bar", x=x, y=y)
    plt.show()