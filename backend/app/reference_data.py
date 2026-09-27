"""模拟数据源: 与前端原型保持一致的项目/风险/来源基准数据."""
from datetime import datetime, timezone

# (风险大类, 根因类别 ID, 具体根因)
RISK_CLASSES: list[tuple[str, str, str]] = [
    ("网络安全运营风险 / 私钥泄露", "infra_admin_key_compromise", "管理员特权私钥被夺权"),
    ("基础设施风险 / 跨链桥验证缺陷", "infra_rpc_node_poisoning", "RPC节点中毒与虚假事件广播"),
    ("经济设计风险 / 预言机操纵", "economic_oracle_signer_compromise", "预言机签名节点私钥泄露"),
    ("社会工程风险 / 终端用户与开发环境劫持", "soc_phishing_developer_device", "开发者设备受诱骗被植入木马"),
    ("智能合约技术风险", "smart_contract_reentrancy", "重入攻击 (Reentrancy)"),
]

# (项目名, 公链, 合约/协议类型)
REAL_WORLD_PROJECTS: list[tuple[str, str, str]] = [
    ("Drift Protocol", "Solana", "DEX/永续合约"),
    ("KelpDAO Bridge", "Ethereum", "流动性质押/跨链桥"),
    ("Ostium Protocol", "Arbitrum", "Perps永续协议"),
    ("Humanity Protocol", "BNB Chain", "代币与Proxy合约"),
    ("Curve Finance", "Ethereum", "AMM流动性池"),
    ("KyberSwap", "Polygon", "DEX 聚合器"),
    ("Euler Finance", "Ethereum", "去中心化借贷"),
    ("Orbit Chain", "Multi-Chain", "跨链节点协议"),
    ("Munchables", "Blast", "GameFi 质押池"),
    ("Hedgey Finance", "Arbitrum", "Token Claim 锁仓合约"),
]

# (报道来源, 来源标识)
SOURCES: list[tuple[str, str]] = [
    ("PeckShield 警报 & TRM Labs 链上追查报告", "peckshield"),
    ("SlowMist 慢雾安全团队 Post-Mortem 报告", "slowmist"),
    ("Beosin EagleEye 警报 & CertiK 审计核查", "beosin"),
    ("BlockSec Phalcon 链上交易重现与分析", "blocksec"),
    ("Chainalysis 专题投研报告 & 官方警报", "chainalysis"),
]

# 事件状态分类 (前端筛选与其一致)
STATUSES: list[str] = ["进行中", "已确认", "已缓解", "白帽拦截", "调查中"]

# 历史事件的基准抓取时间 (与前端原型一致)
BASE_FETCH_TIME: datetime = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
