"""Landing page for transit-lab with navigation to Tracks and Lines."""

import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell
def _():
    from components.navbar import navbar

    return (navbar,)


@app.cell
def _(navbar):
    navbar()
    return


@app.cell
def _():
    import marimo as mo

    mo.md(
        """
        **transit-lab**

        Select **Tracks** or **Lines** from the menu above to get started.
        """
    )
    return (mo,)


if __name__ == "__main__":
    app.run()
