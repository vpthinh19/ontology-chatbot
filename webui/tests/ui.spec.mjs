import { expect, test } from "@playwright/test";

// Không có máy chủ quản trị khi test: mặc định là khách. Test nào cần phiên quản trị thì tự đặt lại.
test.beforeEach(async ({ page }) => {
  await page.route("**/api/admin/**", (route) =>
    route.fulfill({ status: 401, json: { detail: "Chưa đăng nhập quản trị." } }),
  );
});

test("LaTeX arrows in an answer are displayed as ordinary arrows", async ({ page }) => {
  await page.route("**/healthz", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: '{"status":"ok"}' }),
  );
  await page.route("**/chat", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: 'data: {"type":"completed","content":"Bước 1 $\\\\rightarrow$ bước 2"}\n\n',
    }),
  );
  await page.goto("http://127.0.0.1:4173");
  await page.locator(".prompt-input").fill("Kiểm tra mũi tên");
  await page.locator("#send-prompt-btn").click();

  await expect(page.locator(".bot-message:not(.introduction) .message-text").last()).toHaveText(
    "Bước 1 → bước 2",
  );
});

test("the page opens with an introduction in the content column instead of suggested questions", async ({ page }) => {
  await page.route("**/healthz", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: '{"status":"ok"}' }),
  );
  await page.setViewportSize({ width: 1440, height: 900 });

  await page.goto("http://127.0.0.1:4173");

  const introduction = page.locator(".bot-message.introduction");
  await expect(introduction).toContainText("trợ lý học vụ của Trường Đại học Nha Trang");
  await expect(introduction).toContainText("được lưu lại để cải thiện hệ thống");
  await expect(page.locator(".suggestions-item")).toHaveCount(0);
  const column = await page.locator(".chats-container").boundingBox();
  const prompt = await page.locator(".prompt-container").boundingBox();
  expect(Math.abs(column.x - prompt.x)).toBeLessThanOrEqual(1);
  expect(Math.abs(column.width - prompt.width)).toBeLessThanOrEqual(1);

  await page.setViewportSize({ width: 390, height: 844 });
  const mobile = await introduction.boundingBox();
  expect(mobile.x).toBeGreaterThanOrEqual(0);
  expect(mobile.x + mobile.width).toBeLessThanOrEqual(390);
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

test("a streaming answer stops dragging the page down once the reader scrolls up", async ({
  page,
}) => {
  // Luồng do chính phép kiểm điều khiển: đổ chữ vào đúng lúc cần, để chỗ đứng
  // của trang đo được chắc chắn chứ không phụ thuộc nhịp mạng.
  await page.addInitScript(() => {
    const nativeFetch = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      if (!String(input).endsWith("/chat")) return nativeFetch(input, init);
      const encoder = new TextEncoder();
      return new Response(
        new ReadableStream({
          start(controller) {
            window.__push = (count) => {
              for (let index = 0; index < count; index += 1) {
                controller.enqueue(
                  encoder.encode(
                    `data: {"type":"text_delta","content":"Dòng trả lời số ${index}\\n"}\n\n`,
                  ),
                );
              }
            };
          },
        }),
        { status: 200, headers: { "Content-Type": "text/event-stream" } },
      );
    };
  });
  await page.route("**/healthz", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: '{"status":"ok"}' }),
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("http://127.0.0.1:4173");

  await page.locator(".prompt-input").fill("điều kiện xét học bổng");
  await page.locator("#send-prompt-btn").click();
  await page.waitForFunction(() => typeof window.__push === "function");

  const settle = () =>
    page.evaluate(
      () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ),
    );
  const bottomGap = () =>
    page.evaluate(
      () =>
        document.documentElement.scrollHeight - window.scrollY - window.innerHeight,
    );

  await page.evaluate(() => window.__push(80));
  await settle();
  expect(await bottomGap()).toBeLessThanOrEqual(64);

  // Người đọc kéo lên xem lại đoạn trên. Chữ vẫn chảy về, nhưng trang phải đứng
  // yên tại chỗ họ đặt nó.
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.evaluate(() => window.__push(80));
  await settle();
  expect(await page.evaluate(() => window.scrollY)).toBe(0);

  // Quay lại đáy là bám tiếp.
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  await page.evaluate(() => window.__push(80));
  await settle();
  expect(await bottomGap()).toBeLessThanOrEqual(64);
});

test("clearing the conversation brings the introduction back", async ({ page }) => {
  await page.route("**/healthz", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: '{"status":"ok"}' }),
  );
  await page.route("**/chat", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: 'data: {"type":"completed","content":"Câu trả lời thử"}\n\n',
    }),
  );
  await page.goto("http://127.0.0.1:4173");
  await page.locator(".prompt-input").fill("Câu hỏi thử");
  await page.locator("#send-prompt-btn").click();
  await expect(page.locator(".bot-message:not(.introduction) .message-text").last()).toHaveText("Câu trả lời thử");

  await page.locator("#delete-chats-btn").click();

  await expect(page.locator(".message")).toHaveCount(1);
  await expect(page.locator(".bot-message.introduction")).toBeVisible();
});

test("the prompt and its buttons use the same generous corner radius", async ({ page }) => {
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
    };
  });

  expect(shapes.prompt.radius).toBeGreaterThanOrEqual(shapes.prompt.height / 2 - 1);
  expect(shapes.send.width).toBeCloseTo(shapes.send.height, 0);
  expect(shapes.send.radius).toBeGreaterThanOrEqual(shapes.send.width / 2 - 1);
  expect(shapes.theme.width).toBeCloseTo(shapes.theme.height, 0);
  expect(shapes.theme.radius).toBeGreaterThanOrEqual(shapes.theme.width / 2 - 1);
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
      body: 'data: {"type":"completed","content":"Câu trả lời"}\n\n',
    }),
  );
  await page.goto("http://127.0.0.1:4173");

  const deleteButton = page.locator("#delete-chats-btn");
  await expect(deleteButton).toBeVisible();
  await expect(deleteButton).toBeDisabled();

  await page.locator(".prompt-input").fill("Câu hỏi");
  await page.locator("#send-prompt-btn").click();
  await expect(page.locator(".bot-message:not(.introduction) .message-text")).toContainText("Câu trả lời");
  await expect(deleteButton).toBeEnabled();

  await deleteButton.click();
  await expect(page.locator(".message:not(.introduction)")).toHaveCount(0);
  await expect(page.locator(".bot-message.introduction")).toBeVisible();
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

test("a truncated chat stream is not committed as a successful answer", async ({ page }) => {
  await page.route("**/healthz", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: '{"status":"ok"}' }),
  );
  await page.route("**/chat", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: 'data: {"type":"text_delta","content":"Một phần"}\n\n',
    }),
  );
  await page.goto("http://127.0.0.1:4173");
  await page.locator(".prompt-input").fill("Cho tôi câu trả lời đầy đủ");
  await page.locator("#send-prompt-btn").click();

  await expect(page.locator(".bot-message:not(.introduction) .message-text")).toContainText("bị gián đoạn");
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

  await expect(page.locator(".bot-message:not(.introduction) .message-text")).toContainText("đánh thức lại");
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
            'data: {"type":"lookup_sta',
            'rted","keywords":"học phí"}\n\n',
            'data: {"type":"text_delta","content":"Xin ch',
            'ào "}\n\n',
            'data: {"type":"text_delta","content":"bạn"}\n\n',
            'data: {"type":"completed","content":"Xin chào bạn"}\n\n',
          ]
        : [
            'data: {"type":"text_delta","content":"Lượt hai"}\n\n',
            'data: {"type":"completed","content":"Lượt hai"}\n\n',
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
  await expect(page.locator(".bot-message:not(.introduction) .message-text").last()).toContainText("Xin chào bạn");
  await expect(page.locator("#send-prompt-btn")).toBeDisabled();

  await input.fill("Câu nối tiếp");
  await expect(page.locator("#send-prompt-btn")).toBeEnabled();
  await page.locator("#send-prompt-btn").click();
  await expect(page.locator(".bot-message:not(.introduction) .message-text").last()).toContainText("Lượt hai");

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
      body: 'data: {"type":"completed","content":"Câu trả lời"}\n\n',
    });
  });

  await page.goto("http://127.0.0.1:4173");
  await page.locator(".prompt-input").fill("Câu hỏi");
  await page.locator("#send-prompt-btn").click();
  await expect(page.locator(".bot-message:not(.introduction) .message-text")).toContainText("Câu trả lời");

  expect(seen.health).toEqual({
    url: "http://127.0.0.1:4173/api/healthz",
    authorization: undefined,
  });
  expect(seen.chat).toEqual({
    url: "http://127.0.0.1:4173/api/chat",
    authorization: undefined,
  });
});

test("a rejected service key is reported when the question is sent", async ({ page }) => {
  // Trang không còn vòng chờ máy chủ, nên khoá dịch vụ sai chỉ lộ ra lúc gửi câu hỏi.
  await page.route("**/api/chat", (route) =>
    route.fulfill({ status: 401, contentType: "application/json", body: "{}" }),
  );
  await page.goto("http://127.0.0.1:4173");

  await page.locator(".prompt-input").fill("Học phí nộp ở đâu?");
  await page.locator("#send-prompt-btn").click();

  await expect(page.locator(".bot-message").last()).toContainText(
    "từ chối xác thực dịch vụ của trang này",
  );
});

test("the page wakes the server without making the visitor wait for it", async ({ page }) => {
  let probes = 0;
  // Máy chủ đang nguội: lượt đánh thức không bao giờ trả lời.
  await page.route("**/healthz", () => {
    probes += 1;
    return new Promise(() => {});
  });
  await page.route("**/api/chat", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: 'data: {"type": "completed", "content": "Xong"}\n\n',
    }),
  );
  await page.goto("http://127.0.0.1:4173");

  // Không có chấm trạng thái, không có chữ bảo chờ, và nút gửi mở ngay khi có câu hỏi.
  await expect(page.locator(".server-status")).toHaveCount(0);
  await expect(page.getByText("Đang kết nối máy chủ")).toHaveCount(0);
  await page.locator(".prompt-input").fill("Thời gian thu học phí?");
  await expect(page.locator("#send-prompt-btn")).toBeEnabled();

  await page.locator("#send-prompt-btn").click();

  await expect(page.locator(".bot-message").last()).toContainText("Xong");
  expect(probes).toBeGreaterThan(0);
});

// Máy chủ trả lời ngay: các test dưới đây chỉ quan tâm tới ô tài khoản, không quan tâm lượt đánh thức.
const quietServer = async (page) => {
  await page.route("**/healthz", (route) => route.fulfill({ status: 200, json: { status: "ok" } }));
};

test("a visitor sees only an avatar; the guest box and its KEY field open on demand", async ({ page }) => {
  await quietServer(page);
  await page.goto("http://127.0.0.1:4173");

  const avatar = page.getByRole("button", { name: "Tài khoản: khách" });
  await expect(avatar).toBeVisible();
  await expect(page.locator("#account-panel")).toBeHidden();
  await expect(page.getByText("Đăng nhập")).toBeHidden();

  await avatar.click();
  await expect(page.locator("#account-name")).toHaveText("Tài khoản: khách");
  await expect(page.locator("#account-login")).toBeVisible();
  await expect(page.locator("#account-switch")).toBeHidden();
  await expect(page.locator("#account-logout")).toBeHidden();
  await expect(page.locator("#account-form")).toBeHidden();

  await page.click("#account-login");
  await expect(page.locator("#account-password")).toBeFocused();
  await expect(page.locator("#account-password")).toHaveAttribute("placeholder", "KEY");
  await expect(page.locator("#account")).not.toContainText(/mật khẩu|quản trị viên/i);

  await page.keyboard.press("Escape");
  await expect(page.locator("#account-panel")).toBeHidden();
  await expect(avatar).toBeFocused();
});

test("clicking elsewhere closes the account box", async ({ page }) => {
  await quietServer(page);
  await page.goto("http://127.0.0.1:4173");

  await page.getByRole("button", { name: "Tài khoản: khách" }).click();
  await expect(page.locator("#account-panel")).toBeVisible();
  await page.locator(".chats-container").click();
  await expect(page.locator("#account-panel")).toBeHidden();
});

test("a wrong KEY is reported next to the field", async ({ page }) => {
  await quietServer(page);
  await page.route("**/api/admin/login", (route) =>
    route.fulfill({ status: 401, json: { detail: "KEY không đúng." } }),
  );
  await page.goto("http://127.0.0.1:4173");

  await page.getByRole("button", { name: "Tài khoản: khách" }).click();
  await page.click("#account-login");
  await page.fill("#account-password", "sai");
  await page.press("#account-password", "Enter");

  await expect(page.locator("#account-error")).toHaveText("KEY không đúng.");
  await expect(page.getByRole("button", { name: "Tài khoản: khách" })).toBeVisible();
});

test("an admin switches pages and signs out from the account box", async ({ page }) => {
  await quietServer(page);
  let signedIn = false;
  let sentKey = null;
  await page.route("**/api/admin/login", (route) => {
    sentKey = route.request().postDataJSON().key;
    signedIn = true;
    return route.fulfill({ status: 200, json: { ok: true } });
  });
  await page.route("**/api/admin/logout", (route) => {
    signedIn = false;
    return route.fulfill({ status: 200, json: { ok: true } });
  });
  await page.goto("http://127.0.0.1:4173");

  await page.getByRole("button", { name: "Tài khoản: khách" }).click();
  await page.click("#account-login");
  await page.fill("#account-password", "quan-tri");
  await page.press("#account-password", "Enter");

  expect(sentKey).toBe("quan-tri");
  const avatar = page.getByRole("button", { name: "Tài khoản: quản trị" });
  await expect(avatar).toBeVisible();
  await expect(page.locator("#account-panel")).toBeHidden();

  await avatar.click();
  await expect(page.locator("#account-name")).toHaveText("Tài khoản: quản trị");
  await expect(page.locator("#account-switch")).toHaveAttribute("href", "/admin");
  await expect(page.locator("#account-login")).toBeHidden();
  await expect(page.locator("#account-form")).toBeHidden();

  await page.click("#account-logout");
  await expect(page.getByRole("button", { name: "Tài khoản: khách" })).toBeVisible();
  expect(signedIn).toBe(false);
});

test("an open admin session shows the admin account on arrival", async ({ page }) => {
  await quietServer(page);
  await page.route("**/api/admin/session", (route) =>
    route.fulfill({ status: 200, json: { ok: true } }),
  );
  await page.goto("http://127.0.0.1:4173");

  await page.getByRole("button", { name: "Tài khoản: quản trị" }).click();
  await expect(page.locator("#account-switch")).toBeVisible();
});

test("the short admin address asks a guest for the KEY", async ({ page }) => {
  await page.goto("http://127.0.0.1:4173/admin");

  await expect(page.getByRole("heading", { name: "Quản trị ontology" })).toBeVisible();
  await expect(page.locator("#account-password")).toBeFocused();
  await expect(page.locator("#tabs")).toBeHidden();
  // Khách ở trang quản trị: hộp không đóng, vì trang không còn gì khác để làm.
  await page.keyboard.press("Escape");
  await expect(page.locator("#account-password")).toBeVisible();
  await expect(page.locator("#account-switch")).toHaveAttribute("href", "/");
});

test("the chat keeps the session the server issued and starts a new one after clearing", async ({ page }) => {
  await quietServer(page);
  const sent = [];
  await page.route("**/chat", (route) => {
    sent.push(route.request().postDataJSON().session ?? null);
    return route.fulfill({
      status: 200,
      headers: { "Content-Type": "text/event-stream", "X-Chat-Session": `20260919T10000${sent.length}-abcdef` },
      body: 'data: {"type":"completed","content":"Có."}\n\n',
    });
  });
  await page.goto("http://127.0.0.1:4173");
  const ask = async (text) => {
    await page.locator(".prompt-input").fill(text);
    await page.locator("#send-prompt-btn").click();
    await expect(page.locator("body")).not.toHaveClass(/bot-responding/);
  };

  await ask("một");
  await ask("hai");
  await page.locator("#delete-chats-btn").click();
  await ask("ba");

  expect(sent).toEqual([null, "20260919T100001-abcdef", null]);
});
