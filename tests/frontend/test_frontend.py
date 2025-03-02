import pytest
import re
from playwright.sync_api import expect


@pytest.mark.frontend
def test_homepage(web_server, page):
    page.goto("http://localhost:8000")
    assert page.title() == "AiiDA-WorkGraph App"

    # Check if the link to WorkGraph exists
    element = page.locator("a[href='/workgraph']")
    if not element.is_visible():
        pytest.fail("Element 'a[href='/workgraph']' not found on the page")


@pytest.mark.frontend
def test_workgraph(web_server, page, ran_wg_calcfunction):
    page.goto("http://localhost:8000")
    page.click('a[href="/workgraph"]')

    # Check for WorkGraph Table Header
    assert page.get_by_role("heading", name="WorkGraph").is_visible()

    # Check if the search input is visible
    assert page.get_by_placeholder("Search...").is_visible()

    # Check for Table Headers in DataGrid
    assert page.get_by_role("columnheader", name="PK").is_visible()
    assert page.get_by_role("columnheader", name="Created").is_visible()
    assert page.get_by_role("columnheader", name="Process Label").is_visible()
    assert page.get_by_role("columnheader", name="State").is_visible()
    assert page.get_by_role("columnheader", name="Actions").is_visible()

    # Check pagination controls
    assert page.locator(".MuiTablePagination-root").is_visible()

    # Check if at least one row is visible
    page.locator('[data-field="process_label"]').get_by_text(
        "WorkGraph<test_debug_math>"
    ).hover()
    rows = page.get_by_role("row").all()
    assert len(rows) >= 2


@pytest.mark.frontend
def test_workgraph_item(web_server, page, ran_wg_calcfunction):
    page.goto("http://localhost:8000/workgraph/")
    page.get_by_role("link", name=str(ran_wg_calcfunction.pk), exact=True).click()

    assert page.get_by_text("sumdiff3").is_visible()

    # Click "Arrange" button
    page.get_by_role("button", name="Arrange").click()

    gui_node = page.get_by_text("sumdiff2")

    # Check if background color changes
    gui_node_color = gui_node.evaluate(
        "element => window.getComputedStyle(element).backgroundColor"
    )
    assert gui_node_color == "rgba(0, 0, 0, 0)"

    page.locator(".realtime-switch").click()
    page.wait_for_function(
        "selector => !!document.querySelector(selector)",
        arg="div.title[style='background: green;']",
    )

    gui_node_color = gui_node.evaluate(
        "element => window.getComputedStyle(element).backgroundColor"
    )
    assert gui_node_color == "rgb(0, 128, 0)"

    # Check if clicking a node opens the sidebar
    page.locator(".detail-switch").click()
    # pause here for debugging
    # page.pause()
    # page.wait_for_selector('[data-testid="input-x"] input', timeout=5000)  # Wait for up to 5 seconds
    # input_x_control = page.get_by_test_id("input-x").first.locator("input")
    # assert input_x_control.input_value() == "2"
    # Verify that clicking on the gui node will pop up a sidebar
    gui_node.click()
    node_details_sidebar = page.get_by_text("CloseNode")
    node_details_sidebar.wait_for(state="visible")
    assert node_details_sidebar.is_visible()

    node_details_sidebar.get_by_role("button", name="Close").click()
    node_details_sidebar.wait_for(state="hidden")
    assert node_details_sidebar.is_hidden()

    # Check if "Summary" tab works
    page.get_by_role("button", name="Summary").click()
    assert page.get_by_text("typeWorkGraph<test_debug_math>").is_visible()

    # Check if "Log" tab works
    page.get_by_role("button", name="Log").click()
    log_line = (
        page.locator(".log-content")
        .locator("div")
        .filter(has_text=re.compile(r".*Task: sumdiff2 finished.*"))
    )
    log_line.wait_for(state="visible")
    assert log_line.is_visible()

    # Verify that Time  works
    page.get_by_role("button", name="Time").click()
    row = page.locator(".rct-sidebar-row ").get_by_text("sumdiff2")
    row.wait_for(state="visible")
    assert row.is_visible()


@pytest.mark.frontend
def test_datanode_item(web_server, page, ran_wg_calcfunction):
    page.goto("http://localhost:8000/datanode/")
    data_node_pk = ran_wg_calcfunction.nodes["sumdiff1"].inputs["x"].value.pk

    # Click on the link for the specific data node
    page.get_by_role("link", name=str(data_node_pk), exact=True).click()

    # Ensure at least 3 rows exist (header + 2 data rows)
    expect(page.get_by_role("row").nth(2)).to_be_visible()
    assert page.get_by_role("row").count() >= 3

    # Check if "value" column is present in the first data row
    assert page.locator('[data-field="value"]').first.is_visible()

    # Check if "node_type" column is present in the second data row
    assert page.locator('[data-field="node_type"]').first.is_visible()


@pytest.mark.frontend
def test_settings(web_server, page, ran_wg_calcfunction):
    page.goto("http://localhost:8000/settings/")
    # Verify that only one row is visible
    expect(page.locator(":nth-match(tr, 1)")).to_be_visible()
    expect(page.locator(":nth-match(tr, 2)")).to_be_hidden()

    # Verify that after starting the daemon one additional row appeared
    page.get_by_role("button", name="Start Daemon").click()
    expect(page.locator(":nth-match(tr, 2)")).to_be_visible()
    expect(page.locator(":nth-match(tr, 3)")).to_be_hidden()

    # Verify that after adding workers one additional row appeared
    page.get_by_role("button", name="Increase Workers").click()
    expect(page.locator(":nth-match(tr, 3)")).to_be_visible()
    expect(page.locator(":nth-match(tr, 4)")).to_be_hidden()

    # Verify that after decreasing workers one row disappears
    page.get_by_role("button", name="Decrease Workers").click()
    expect(page.locator(":nth-match(tr, 2)")).to_be_visible()
    expect(page.locator(":nth-match(tr, 3)")).to_be_hidden()

    # Verify that stopping the daemon only the header row exists
    page.get_by_role("button", name="Stop Daemon").click()
    expect(page.locator(":nth-match(tr, 1)")).to_be_visible()
    expect(page.locator(":nth-match(tr, 2)")).to_be_hidden()


############################
# Tests mutating the state #
############################
# The tests below change the state of the aiida database and cannot necessary be executed in arbitrary order.


@pytest.mark.frontend
def test_workgraph_delete(web_server, page, ran_wg_calcfunction):
    """Tests deleting the last WorkGraph node in DataGrid."""
    page.goto("http://localhost:8000/workgraph")

    # Ensure the last row is visible
    last_row = page.get_by_role("row").last()
    expect(last_row).to_be_visible()

    # Get delete button in the last row
    delete_button = last_row.get_by_role("button", name="Delete")

    # Verify canceling deletion does not remove the row
    delete_button.click()
    expect(page.get_by_text("Confirm deletion")).to_be_visible()
    page.get_by_role("button", name="Cancel").click()
    expect(last_row).to_be_visible()

    # Confirm deletion
    delete_button.click()
    expect(page.get_by_text("Confirm deletion")).to_be_visible()
    page.get_by_role("button", name="Confirm").click()
    expect(last_row).to_be_hidden()


@pytest.mark.frontend
def test_datanode_delete(web_server, page, ran_wg_calcfunction):
    """Tests deleting the last DataNode in DataGrid."""
    page.goto("http://localhost:8000/datanode")

    # Ensure last row is visible
    last_row = page.get_by_role("row").last()
    expect(last_row).to_be_visible()

    # Get delete button in the last row
    delete_button = last_row.get_by_role("button", name="Delete")

    # Verify canceling deletion does not remove the row
    delete_button.click()
    expect(page.get_by_text("Confirm deletion")).to_be_visible()
    page.get_by_role("button", name="Cancel").click()
    expect(last_row).to_be_visible()

    # Confirm deletion
    delete_button.click()
    expect(page.get_by_text("Confirm deletion")).to_be_visible()
    page.get_by_role("button", name="Confirm").click()
    expect(last_row).to_be_hidden()
