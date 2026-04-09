# 飞书通知配置指南

## 问题总结

之前飞书通知无法发送的原因是：**任务创建的用户ID与飞书配置的用户ID不匹配**。

- 飞书配置属于：`user_9343820d`
- 待办任务创建给了：`test_user` 和 `default_user`

## 解决方案

### 方案1：为当前用户配置飞书（推荐）

如果您希望继续使用当前的用户ID（如 `test_user`），需要为该用户也配置飞书应用：

1. **在飞书开放平台获取配置信息**
   - 访问 https://open.feishu.cn/app
   - 创建应用或选择已有应用
   - 获取 `App ID` 和 `App Secret`
   - 给用户发送消息获取 `open_id`

2. **通过API配置飞书**

```bash
curl -X POST http://localhost:8000/api/platform/lark/config \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your_user_id",
    "app_id": "cli_xxxxx",
    "app_secret": "xxxxx",
    "receive_id": "ou_xxxxx",
    "receive_id_type": "open_id"
  }'
```

### 方案2：使用已配置飞书的用户

修改前端默认用户ID为已配置飞书的用户：

编辑 `frontend/src/stores/user.js`：

```javascript
// 第7行
const userId = ref(localStorage.getItem('memorymate_user_id') || 'user_9343820d')
```

然后重新登录前端。

### 方案3：清除浏览器缓存重新生成用户

如果之前没有特意设置过用户ID，可以：

1. 清除浏览器 localStorage 中的 `memorymate_user_id`
2. 刷新页面，系统会自动生成新用户
3. 在飞书配置页面为新用户配置飞书应用

## 验证配置

配置完成后，可以通过以下方式验证：

```bash
# 测试飞书连接
curl http://localhost:8000/api/platform/lark/connection?user_id=your_user_id

# 发送测试消息
curl -X POST http://localhost:8000/api/platform/lark/send \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your_user_id",
    "title": "测试消息",
    "content": "如果您收到这条消息，说明飞书配置成功！"
  }'
```

## 使用流程

正确配置后，使用流程如下：

1. **上传会议文档** → 系统解析提取待办
2. **选择待办并设置提醒时间** → 点击确认
3. **系统检查飞书配置** → 如无配置会提示警告
4. **任务到期** → 自动发送飞书消息提醒

## 注意事项

1. 每个用户需要单独配置飞书应用凭证
2. 任务的提醒时间与用户绑定，不能跨用户共享飞书配置
3. 如果用户未配置飞书，任务仍会创建，但到期时不会收到飞书通知（只会收到WebSocket通知）
