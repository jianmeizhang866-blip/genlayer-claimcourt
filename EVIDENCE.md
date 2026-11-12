# 实测证据（StudioNet，2026-11-12 已全部跑通）

部署者地址（CLI 账号）：`0xd4d734b0c8023e8b9a42913f141a08502afae6f0`
网络：StudioNet（chainId 61999，RPC `https://studio.genlayer.com/api`）

## 1. ClaimCourt — 网页裁决
- 合约：`0xC9f54a88d070753DE30169414336E91e55142DF3`
- 部署 tx：`0xabda533eed331de3bb1686a3d42bb93a20d37899bd8489480b830c72e3732a78`
- 调用 `resolve("Bitcoin was created before 2010", "https://en.wikipedia.org/wiki/Bitcoin")`
  - tx：`0x7ac483452e57b15c31f172cae9d0588895ee0173b992b33fd18c323df7389f21`
- 读回 `last()`：
```json
{"claim": "Bitcoin was created before 2010",
 "claim_id": "1",
 "evidence": "Initial release 0.1.0 / 9 January 2009 (17 years ago)",
 "source": "https://en.wikipedia.org/wiki/Bitcoin",
 "verdict": "TRUE"}
```

## 2. SourceWatch — 稳定字段抽取
- 合约：`0x36a865a1490E4e43400147a1EA61b8E0500a295a`
- 部署 tx：`0x306d480ba1cbb8772484aacc9bdec433527cfde8df80ae42d3e79e365f93c605`
- 调用 `watch("btc", "https://en.wikipedia.org/wiki/Bitcoin", "ticker,launch_year")`
  - tx：`0x0a96b0ab99a5656169485b5e180f2c6ca41ee652774df1cb4310eeea708bb27d`
- 读回 `latest("btc")`：
```json
{"fields": {"launch_year": "2009", "ticker": "BTC"},
 "round": 1,
 "source": "https://en.wikipedia.org/wiki/Bitcoin",
 "watch_id": "btc"}
```

## 3. EscrowGate — 确定性结算
- 合约：`0x885934cFCCF99415e2296dF9EB3ad66520F14376`
- 部署 tx：`0xdedb5721d8ba1edecba8fc41d074d868b4e1c1df8de48525c843afd90f416a28`
- `open_deal("d1", "buyer.eth", "seller.eth", 100, "https://example.com/terms")`
  - tx：`0xea38be76b0a48cb13cbe400179448daeb82b954636077533cb544803f9c83ce1`
- `settle("d1", "TRUE", "claimcourt:1")`
  - tx：`0x8e6d45783eda829c6a6af466d95885951f9ba6e1138f56502919306f8bb97bd5`
- 读回 `get("d1")`：
```json
{"amount": "100", "buyer": "buyer.eth", "deal_id": "d1",
 "evidence": "claimcourt:1", "seller": "seller.eth",
 "status": "SETTLED_TRUE", "terms": "https://example.com/terms"}
```

## 复现命令

```bash
export NODE_USE_ENV_PROXY=1 HTTP_PROXY=http://127.0.0.1:17307 HTTPS_PROXY=http://127.0.0.1:17307
genlayer network set studionet
genlayer account create --name agentfarm --password '<pw>'
genlayer account unlock --account agentfarm --password '<pw>'
genlayer deploy --contract claim_court.py
genlayer write <addr> resolve --args "Bitcoin was created before 2010" "https://en.wikipedia.org/wiki/Bitcoin"
genlayer call <addr> last
```

## 踩到的两个 SDK 坑（已修）

1. **TreeMap 必须在 `__init__` 里实例化**（`self.x = TreeMap()`），只写类型注解不赋值 → 部署时 `contract_error exit_code 1`。
2. **存储里不能用 Python `int`**：`total: int` 会抛 `TypeError: use bigint or one of sized integers`。
   改成 `total: str` 自增，或把数值当字符串存；参数位置仍然可以用 `int`（例如 `open_deal(..., amount: int, ...)` 存 `str(amount)`）。
3. CLI 无法把数字当字符串传（`--args 1` 会按 int 解析），所以 `claim_id` 这类键读的时候要用无参视图（我加了 `last()`）。
