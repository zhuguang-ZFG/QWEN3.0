# LiMa JavaScript SDK

Official JavaScript SDK for [LiMa](https://chat.donglicao.com).

## Install

```bash
npm install lima-sdk
```

## Quick start

```javascript
import { LiMaClient } from "lima-sdk";

const client = new LiMaClient(process.env.LIMA_API_KEY);

const completion = await client.chat.create({
  model: "lima-1.3",
  messages: [{ role: "user", content: "你好" }],
});
console.log(completion.choices[0].message.content);

// List devices
const { devices } = await client.devices.list();
console.log(devices);

// Create a device task
const task = await client.devices.createTask("dev_xxx", { text: "画一只猫" });
console.log(task.taskId);
```

## Streaming

```javascript
const stream = await client.chat.create({
  model: "lima-1.3",
  messages: [{ role: "user", content: "讲个故事" }],
  stream: true,
});

for await (const chunk of stream) {
  const delta = chunk.choices?.[0]?.delta?.content;
  if (delta) process.stdout.write(delta);
}
```

## Error handling

```javascript
import { LiMaAPIError } from "lima-sdk";

try {
  await client.devices.get("unknown_id");
} catch (err) {
  if (err instanceof LiMaAPIError) {
    console.error(err.statusCode, err.message);
  }
}
```

## TypeScript

Type declarations are included under `types/index.d.ts`.
