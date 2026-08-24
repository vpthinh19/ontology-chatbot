import { expect, test } from "@playwright/test";

test("the page announces a cold start before the first health probe returns", async ({ page }) => {
  await page.route("**/healthz", () => new Promise(() => {}));

  await page.goto("http://127.0.0.1:4173", { waitUntil: "domcontentloaded" });

  await expect(page.locator(".server-status")).toContainText(
    "Đang khởi động máy chủ",
    { timeout: 500 },
  );
  await expect(page.locator(".prompt-input")).toBeEnabled();
  await expect(page.locator("#send-prompt-btn")).toBeDisabled();
});

test("suggestions share the content column and remain comfortably readable", async ({ page }) => {
  await page.route("**/healthz", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: '{"status":"ok"}' }),
  );
  await page.setViewportSize({ width: 1440, height: 900 });

  await page.goto("http://127.0.0.1:4173");

  const header = await page.locator(".app-header").boundingBox();
  const suggestions = await page.locator(".suggestions").boundingBox();
  const firstCard = await page.locator(".suggestions-item").first().boundingBox();
  expect(header).not.toBeNull();
  expect(suggestions).not.toBeNull();
  expect(firstCard).not.toBeNull();
  expect(Math.abs(suggestions.x - header.x)).toBeLessThanOrEqual(1);
  expect(Math.abs(suggestions.width - header.width)).toBeLessThanOrEqual(1);
  expect(firstCard.width).toBeGreaterThan(320);

  await page.setViewportSize({ width: 390, height: 844 });
  const mobileCards = await page.locator(".suggestions-item").evaluateAll((items) =>
    items.map((item) => {
      const { x, y, width, height } = item.getBoundingClientRect();
      return { x, y, width, height };
    }),
  );
  expect(mobileCards).toHaveLength(4);
  expect(mobileCards.every((card) => card.x >= 0 && card.x + card.width <= 390)).toBe(true);
  expect(mobileCards[1].y).toBeGreaterThan(mobileCards[0].y + mobileCards[0].height - 1);
});

test("the composer stays pinned to the viewport bottom while the page scrolls", async ({ page }) => {
  await page.route("**/healthz", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: '{"status":"ok"}' }),
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("http://127.0.0.1:4173");

  const composer = page.locator(".prompt-container");
  const distanceFromBottom = async () => {
    const box = await composer.boundingBox();
    expect(box).not.toBeNull();
    return Math.abs(844 - (box.y + box.height));
  };

  expect(await distanceFromBottom()).toBeLessThanOrEqual(1);

  await page.evaluate(() => {
    document.body.classList.add("chats-active");
    const conversation = document.querySelector(".chats-container");
    conversation.style.minHeight = "1800px";
  });
  await page.evaluate(() => window.scrollTo(0, 700));
  expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
  expect(await distanceFromBottom()).toBeLessThanOrEqual(1);
});

test("the final chat message scrolls fully clear of the fixed composer", async ({ page }) => {
  await page.route("**/healthz", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: '{"status":"ok"}' }),
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("http://127.0.0.1:4173");

  await page.evaluate(() => {
    document.body.classList.add("chats-active");
    const conversation = document.querySelector(".chats-container");
    const filler = document.createElement("div");
    filler.style.height = "1600px";
    const message = document.createElement("article");
    message.className = "message bot-message";
    message.innerHTML = '<div id="last-message" class="message-text">Tin nhắn cuối</div>';
    conversation.replaceChildren(filler, message);
  });
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));

  const lastMessage = await page.locator("#last-message").boundingBox();
  const composer = await page.locator(".prompt-container").boundingBox();
  expect(lastMessage).not.toBeNull();
  expect(composer).not.toBeNull();
  expect(lastMessage.y + lastMessage.height).toBeLessThanOrEqual(composer.y);
});

test("the landing header starts directly with the greeting", async ({ page }) => {
  await page.route("**/healthz", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: '{"status":"ok"}' }),
  );

  await page.goto("http://127.0.0.1:4173");

  await expect(page.getByText("NTU Academic Assistant", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Xin chào" })).toBeVisible();
});

test("the prompt and recommendations use the same generous corner radius", async ({ page }) => {
  await page.route("**/healthz", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: '{"status":"ok"}' }),
  );
  await page.goto("http://127.0.0.1:4173");

  const shapes = await page.evaluate(() => {
    const measure = (selector) => {
      const element = document.querySelector(selector);
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return { width: rect.width, height: rect.height, radius: parseFloat(style.borderTopLeftRadius) };
    };
    return {
      prompt: measure(".prompt-form"),
      send: measure("#send-prompt-btn"),
      theme: measure("#theme-toggle-btn"),
      card: measure(".suggestions-item"),
    };
  });

  expect(shapes.prompt.radius).toBeGreaterThanOrEqual(shapes.prompt.height / 2 - 1);
  expect(shapes.send.width).toBeCloseTo(shapes.send.height, 0);
  expect(shapes.send.radius).toBeGreaterThanOrEqual(shapes.send.width / 2 - 1);
  expect(shapes.theme.width).toBeCloseTo(shapes.theme.height, 0);
  expect(shapes.theme.radius).toBeGreaterThanOrEqual(shapes.theme.width / 2 - 1);
  expect(shapes.card.radius).toBeGreaterThanOrEqual(28);
});

test("focusing the prompt does not draw a rectangular outline", async ({ page }) => {
  await page.route("**/healthz", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: '{"status":"ok"}' }),
  );
  await page.goto("http://127.0.0.1:4173");

  const input = page.locator(".prompt-input");
  await input.focus();

  const outline = await input.evaluate((element) => {
    const style = getComputedStyle(element);
    return { style: style.outlineStyle, width: style.outlineWidth };
  });
  expect(outline).toEqual({ style: "none", width: "0px" });
});

test("delete history stays visible and is enabled only while a conversation exists", async ({ page }) => {
  await page.route("**/healthz", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: '{"status":"ok"}' }),
  );
  await page.route("**/chat", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: 'data: {"loai":"xong","noi_dung":"Câu trả lời"}\n\n',
    }),
  );
  await page.goto("http://127.0.0.1:4173");

  const deleteButton = page.locator("#delete-chats-btn");
  await expect(deleteButton).toBeVisible();
  await expect(deleteButton).toBeDisabled();

  await page.locator(".prompt-input").fill("Câu hỏi");
  await page.locator("#send-prompt-btn").click();
  await expect(page.locator(".bot-message .message-text")).toContainText("Câu trả lời");
  await expect(deleteButton).toBeEnabled();

  await deleteButton.click();
  await expect(page.locator(".message")).toHaveCount(0);
  await expect(deleteButton).toBeDisabled();
});

test("the built frontend sends health probes through the same-origin proxy", async ({ page }) => {
  let proxyWasProbed = false;
  let authorization;
  await page.route("http://127.0.0.1:4173/api/healthz", (route) => {
    proxyWasProbed = true;
    authorization = route.request().headers()["authorization"];
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: '{"status":"ok"}',
    });
  });
  await page.route("https://lightning.example.test/healthz", (route) =>
    route.fulfill({ status: 418 }),
  );

  await page.goto("http://127.0.0.1:4173");

  await expect.poll(() => proxyWasProbed, { timeout: 1_500 }).toBe(true);
  expect(authorization).toBeUndefined();
});

test("revalidating a stale ready tab disables send until the new probe succeeds", async ({ page }) => {
  let probes = 0;
  await page.route("**/healthz", (route) => {
    probes += 1;
    if (probes === 1) {
      return route.fulfill({ status: 200, contentType: "application/json", body: '{"status":"ok"}' });
    }
    return new Promise(() => {});
  });
  await page.goto("http://127.0.0.1:4173");
  await page.locator(".prompt-input").fill("Câu hỏi vẫn còn đây");
  await expect(page.locator("#send-prompt-btn")).toBeEnabled();

  await page.evaluate(() => {
    const actualNow = Date.now;
    Date.now = () => actualNow() + 31_000;
    document.dispatchEvent(new Event("visibilitychange"));
  });

  await expect(page.locator(".server-status")).toContainText("Đang khởi động", { timeout: 500 });
  await expect(page.locator("#send-prompt-btn")).toBeDisabled();
  await expect(page.locator(".prompt-input")).toHaveValue("Câu hỏi vẫn còn đây");
});

test("an old health probe cannot overwrite an offline state", async ({ page }) => {
  let pendingProbe;
  await page.route("**/healthz", (route) => {
    pendingProbe = route;
    return new Promise(() => {});
  });
  await page.goto("http://127.0.0.1:4173", { waitUntil: "domcontentloaded" });
  await expect.poll(() => Boolean(pendingProbe)).toBe(true);

  await page.evaluate(() => {
    Object.defineProperty(navigator, "onLine", { configurable: true, get: () => false });
    window.dispatchEvent(new Event("offline"));
  });
  await pendingProbe.fulfill({ status: 200, contentType: "application/json", body: '{"status":"ok"}' });

  await expect(page.locator(".server-status")).toContainText("mất kết nối", { timeout: 500 });
  await expect(page.locator(".server-status")).toHaveAttribute("data-state", "offline");
});

test("a truncated chat stream is not committed as a successful answer", async ({ page }) => {
  await page.route("**/healthz", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: '{"status":"ok"}' }),
  );
  await page.route("**/chat", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: 'data: {"loai":"chu","noi_dung":"Một phần"}\n\n',
    }),
  );
  await page.goto("http://127.0.0.1:4173");
  await page.locator(".prompt-input").fill("Cho tôi câu trả lời đầy đủ");
  await page.locator("#send-prompt-btn").click();

  await expect(page.locator(".bot-message .message-text")).toContainText("bị gián đoạn");
});

test("a cold failure after send restores the question for a retry", async ({ page }) => {
  await page.route("**/healthz", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: '{"status":"ok"}' }),
  );
  await page.route("**/chat", (route) => route.fulfill({ status: 503, body: "" }));
  await page.goto("http://127.0.0.1:4173");
  const input = page.locator(".prompt-input");
  await input.fill("Học phí bao nhiêu?");
  await page.locator("#send-prompt-btn").click();

  await expect(page.locator(".bot-message .message-text")).toContainText("đánh thức lại");
  await expect(input).toHaveValue("Học phí bao nhiêu?");
});

test("fragmented successful streams complete and become history for the next turn", async ({ page }) => {
  await page.addInitScript(() => {
    const nativeFetch = window.fetch.bind(window);
    window.__chatBodies = [];
    window.fetch = async (input, init) => {
      if (!String(input).endsWith("/chat")) return nativeFetch(input, init);
      window.__chatBodies.push(JSON.parse(init.body));
      const first = window.__chatBodies.length === 1;
      const chunks = first
        ? [
            'data: {"loai":"tra_c',
            'uu","tu_khoa":"học phí"}\n\n',
            'data: {"loai":"chu","noi_dung":"Xin ch',
            'ào "}\n\n',
            'data: {"loai":"chu","noi_dung":"bạn"}\n\n',
            'data: {"loai":"xong","noi_dung":"Xin chào bạn"}\n\n',
          ]
        : [
            'data: {"loai":"chu","noi_dung":"Lượt hai"}\n\n',
            'data: {"loai":"xong","noi_dung":"Lượt hai"}\n\n',
          ];
      const encoder = new TextEncoder();
      return new Response(
        new ReadableStream({
          start(controller) {
            let index = 0;
            const push = () => {
              if (index === chunks.length) {
                controller.close();
                return;
              }
              controller.enqueue(encoder.encode(chunks[index++]));
              setTimeout(push, 0);
            };
            push();
          },
        }),
        { status: 200, headers: { "Content-Type": "text/event-stream" } },
      );
    };
  });
  await page.route("**/healthz", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: '{"status":"ok"}' }),
  );
  await page.goto("http://127.0.0.1:4173");

  const input = page.locator(".prompt-input");
  await input.fill("Câu đầu");
  await page.locator("#send-prompt-btn").click();
  await expect(page.locator(".bot-message .message-text").last()).toContainText("Xin chào bạn");
  await expect(page.locator("#send-prompt-btn")).toBeDisabled();

  await input.fill("Câu nối tiếp");
  await expect(page.locator("#send-prompt-btn")).toBeEnabled();
  await page.locator("#send-prompt-btn").click();
  await expect(page.locator(".bot-message .message-text").last()).toContainText("Lượt hai");

  const bodies = await page.evaluate(() => window.__chatBodies);
  expect(bodies[1].history).toEqual([
    { role: "user", content: "Câu đầu" },
    { role: "assistant", content: "Xin chào bạn" },
  ]);
});

test("browser health and chat calls stay same-origin and carry no authorization", async ({ page }) => {
  const seen = {};
  await page.route("**/api/healthz", (route) => {
    seen.health = {
      url: route.request().url(),
      authorization: route.request().headers()["authorization"],
    };
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: '{"status":"ok"}',
    });
  });
  await page.route("**/api/chat", (route) => {
    seen.chat = {
      url: route.request().url(),
      authorization: route.request().headers()["authorization"],
    };
    return route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: 'data: {"loai":"xong","noi_dung":"Câu trả lời"}\n\n',
    });
  });

  await page.goto("http://127.0.0.1:4173");
  await page.locator(".prompt-input").fill("Câu hỏi");
  await page.locator("#send-prompt-btn").click();
  await expect(page.locator(".bot-message .message-text")).toContainText("Câu trả lời");

  expect(seen.health).toEqual({
    url: "http://127.0.0.1:4173/api/healthz",
    authorization: undefined,
  });
  expect(seen.chat).toEqual({
    url: "http://127.0.0.1:4173/api/chat",
    authorization: undefined,
  });
});

test("a rejected key is reported plainly instead of being retried for minutes", async ({ page }) => {
  let probes = 0;
  await page.route("**/healthz", (route) => {
    probes += 1;
    return route.fulfill({ status: 401, contentType: "application/json", body: "{}" });
  });

  await page.goto("http://127.0.0.1:4173");

  await expect(page.locator(".server-status")).toContainText("từ chối khoá truy cập");
  await expect(page.locator(".server-status")).toHaveAttribute("data-state", "blocked");
  await expect(page.locator("#send-prompt-btn")).toBeDisabled();

  // Vòng đánh thức phải dừng hẳn: khoá sai thì lần probe thứ hai cũng sai, mà
  // lịch giãn dần sẽ còn gõ cửa suốt ba phút nếu nó coi đây là lỗi tạm thời.
  const after = probes;
  await page.waitForTimeout(2_500);
  expect(probes).toBe(after);
});
