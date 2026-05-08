<template>
  <div class="shutdownPage">
    <main class="shutdownCard" aria-labelledby="shutdownTitle">
      <p class="badge">服务状态：已停服</p>
      <h1 id="shutdownTitle">ConvertAPK 工具站停服公告</h1>
      <p class="lead">
        经发现有不法人员利用本站制作非法程序。为履行社会责任、避免风险继续扩散，已于 2026 年 5 月 8 日起停止本站全部在线服务。
      </p>

      <section class="sectionBlock" aria-labelledby="apologyTitle">
        <h2 id="apologyTitle">郑重致歉</h2>
        <p>
          对于此次事件可能给开发者带来的担忧和影响，深表歉意，将持续推进事件核查，严肃追查该任务线，杜绝此类任务构建。
        </p>
      </section>

      <section class="sectionBlock" aria-labelledby="handlingTitle">
        <h2 id="handlingTitle">当前处置进展</h2>
        <ul>
          <li>已全面关闭在线构建与下载能力，防止新增风险产物生成。</li>
          <li>已启动任务链路追查，固定关键日志与审计信息。</li>
          <li>正在逐步清理历史风险任务与相关缓存文件。</li>
        </ul>
      </section>

    
      <footer class="footer">
        <p>感谢大家的理解与监督。</p>
        <p>ConvertAPK</p>
        <p>2026 年 5 月 8 日</p>
      </footer>
    </main>
  </div>
</template>

<style scoped>
:global(*) {
  box-sizing: border-box;
}

:global(body) {
  margin: 0;
  min-height: 100vh;
  font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  color: #f3f4f6;
  background:
    radial-gradient(circle at 14% 18%, rgba(127, 29, 29, 0.55), transparent 42%),
    radial-gradient(circle at 82% 80%, rgba(17, 24, 39, 0.75), transparent 38%),
    #0b1220;
}

.shutdownPage {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.shutdownCard {
  width: min(860px, 100%);
  border: 1px solid rgba(248, 113, 113, 0.3);
  border-radius: 20px;
  padding: 32px;
  backdrop-filter: blur(2px);
  background: linear-gradient(160deg, rgba(12, 18, 31, 0.94), rgba(20, 29, 48, 0.88));
  box-shadow: 0 28px 50px rgba(0, 0, 0, 0.4);
}

.badge {
  display: inline-block;
  margin: 0 0 14px;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid rgba(252, 165, 165, 0.35);
  background: rgba(220, 38, 38, 0.2);
  color: #fecaca;
  font-size: 13px;
  font-weight: 600;
}

h1 {
  margin: 0;
  color: #fee2e2;
  font-size: clamp(28px, 4vw, 38px);
  line-height: 1.24;
}

h2 {
  margin: 0 0 10px;
  color: #fca5a5;
  font-size: 20px;
}

p {
  margin: 0;
  line-height: 1.8;
}

.lead {
  margin-top: 16px;
  color: #e5e7eb;
  font-size: 16px;
}

.sectionBlock {
  margin-top: 26px;
  padding-top: 20px;
  border-top: 1px solid rgba(248, 113, 113, 0.2);
}

ul {
  margin: 0;
  padding-left: 20px;
  line-height: 1.9;
  color: #f3f4f6;
}

.footer {
  margin-top: 28px;
  padding-top: 18px;
  border-top: 1px dashed rgba(248, 113, 113, 0.25);
  color: #d1d5db;
}

@media (max-width: 640px) {
  .shutdownPage {
    padding: 14px;
  }

  .shutdownCard {
    padding: 22px;
    border-radius: 16px;
  }

  h2 {
    font-size: 18px;
  }
}
</style>
