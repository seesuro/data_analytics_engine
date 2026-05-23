# Plotting tools implementation
from pathlib import Path
from uuid import uuid4

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from contracts import ArtifactRef


def plot_bar(df, x, y):
    df.plot(kind="bar", x=x, y=y)
    plt.show()


def save_bar_chart(df, x, y, artifact_dir: str | Path) -> ArtifactRef:
    output_dir = Path(artifact_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"bar_{uuid4().hex}.png"

    ax = df.plot(kind="bar", x=x, y=y)
    fig = ax.get_figure()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)

    return ArtifactRef(artifact_type="chart", path=path, mime_type="image/png")
