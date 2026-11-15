from datetime import datetime

from conftest import ADMIN, TZ, USER


def callback_data(markup):
    return [b["callback_data"] for row in markup["inline_keyboard"] for b in row if "callback_data" in b]


def fill_cart(driver):
    driver.text("/start")
    driver.tap("menu")
    driver.tap("cat:mains")
    driver.tap("add:plov")
    driver.tap("add:plov")
    driver.tap("cat:bakery")
    driver.tap("add:samsa")


def checkout(driver, name="Aziza", phone="+998 90 123 45 67", slot="slot:1230"):
    driver.tap("checkout")
    driver.text(name)
    driver.text(phone)
    driver.tap(slot)


def test_start_shows_cafe_and_buttons(driver, client):
    driver.text("/start")
    call = client.last("send", USER)
    assert "Kazan &amp; Tandoor" in call["text"]
    assert callback_data(call["markup"]) == ["menu", "cart"]


def test_browsing_and_adding_updates_cart(driver, client, bot):
    fill_cart(driver)
    assert bot.session(USER).cart.quantities == {"plov": 2, "samsa": 1}
    assert client.last("answer")["text"] == "Beef samsa added (1 in cart)"
    edited = client.last("edit", USER)
    assert "🛒 Cart · $22.00" in [b["text"] for row in edited["markup"]["inline_keyboard"] for b in row]


def test_cart_plus_minus_and_clear(driver, client, bot):
    fill_cart(driver)
    driver.tap("cart")
    assert "Total: $22.00" in client.last("edit", USER)["text"]
    driver.tap("dec:plov")
    driver.tap("inc:samsa")
    assert bot.session(USER).cart.quantities == {"plov": 1, "samsa": 2}
    assert "Total: $15.50" in client.last("edit", USER)["text"]
    driver.tap("clear")
    assert "cart is empty" in client.last("edit", USER)["text"]


def test_checkout_with_empty_cart_is_refused(driver, client, bot):
    driver.text("/start")
    driver.tap("checkout")
    assert client.last("answer")["text"] == "Your cart is empty"
    assert bot.session(USER).state is None


def test_full_order_notifies_admin_and_saves(driver, client, bot, store):
    fill_cart(driver)
    checkout(driver)
    summary = client.last("send", USER)
    assert "Check your order" in summary["text"]
    assert "Pickup today at 12:30" in summary["text"]
    driver.tap("confirm")

    confirmation = client.last("edit", USER)
    assert "Order #1 received" in confirmation["text"]
    admin = client.last("send", ADMIN)
    assert "Order #1" in admin["text"] and "Aziza" in admin["text"] and "+998901234567" in admin["text"]
    assert "2 × Tashkent plov — $19.00" in admin["text"]
    assert callback_data(admin["markup"]) == ["adm:accepted:1", "adm:cancelled:1"]

    order = store.get(1)
    assert order.total == 22.0 and order.status == "new"
    assert order.pickup_at == datetime(2026, 11, 14, 12, 30, tzinfo=TZ)
    assert bot.session(USER).cart.is_empty() and bot.session(USER).state is None


def test_phone_can_be_shared_as_contact(driver, client, bot):
    fill_cart(driver)
    driver.tap("checkout")
    driver.text("Aziza")
    driver.contact("998901112233")
    assert bot.session(USER).phone == "998901112233"
    assert bot.session(USER).state == "time"


def test_invalid_inputs_keep_the_step(driver, client, bot):
    fill_cart(driver)
    driver.tap("checkout")
    driver.text("A")
    assert bot.session(USER).state == "name"
    driver.text("Aziza")
    driver.text("not a phone")
    assert bot.session(USER).state == "phone"
    driver.text("+998 90 123 45 67")
    driver.text("12:10")
    assert "at least 20 minutes" in client.last("send", USER)["text"]
    driver.text("19:45")
    assert bot.session(USER).state == "confirm"


def test_cancel_keeps_cart(driver, client, bot):
    fill_cart(driver)
    driver.tap("checkout")
    driver.text("/cancel")
    assert bot.session(USER).state is None
    assert bot.session(USER).cart.count == 3


def test_closed_for_the_day(driver, client, bot, clock):
    clock["now"] = datetime(2026, 11, 14, 21, 55, tzinfo=TZ)
    fill_cart(driver)
    driver.tap("checkout")
    driver.text("Aziza")
    driver.text("+998901234567")
    assert "closed for today" in client.last("send", USER)["text"]
    assert bot.session(USER).state is None


def test_admin_status_flow_notifies_customer(driver, client, store):
    fill_cart(driver)
    checkout(driver)
    driver.tap("confirm")

    driver.tap("adm:accepted:1", user=ADMIN, chat=ADMIN)
    assert "accepted and being prepared" in client.last("send", USER)["text"]
    driver.tap("adm:ready:1", user=ADMIN, chat=ADMIN)
    assert "is ready" in client.last("send", USER)["text"]
    assert store.get(1).status == "ready"
    assert client.last("edit", ADMIN)["markup"] is None

    driver.tap("adm:cancelled:1", user=ADMIN, chat=ADMIN)
    assert client.last("answer")["text"] == "Order is already ready"


def test_admin_buttons_ignored_outside_admin_chat(driver, client, store):
    fill_cart(driver)
    checkout(driver)
    driver.tap("confirm")
    driver.tap("adm:cancelled:1")
    assert client.last("answer")["text"] == "Not allowed"
    assert store.get(1).status == "new"


def test_user_input_is_html_escaped(driver, client):
    fill_cart(driver)
    checkout(driver, name="<b>Bob</b>")
    assert "&lt;b&gt;Bob&lt;/b&gt;" in client.last("send", USER)["text"]


def test_two_customers_have_separate_carts(driver, bot):
    driver.tap("add:plov", user=1)
    driver.tap("add:samsa", user=2)
    assert bot.session(1).cart.quantities == {"plov": 1}
    assert bot.session(2).cart.quantities == {"samsa": 1}
