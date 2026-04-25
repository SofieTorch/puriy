"""Landing page for transit-lab with navigation to notebook pages."""

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

        Select **Tracks**, **Lines**, or **Reconstruction** from the menu above to get started.
        """
    )
    return (mo,)


if __name__ == "__main__":
    app.run()
