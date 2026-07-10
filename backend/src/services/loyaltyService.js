import User from "../models/User.js";

/**
 * Simple loyalty (per decisions): visit count, cumulative orders/spend, rank, points.
 * Recomputed on each committed order.
 */
export function applyOrderToStats(user, order) {
  const now = new Date();
  user.stats = user.stats || {};
  user.stats.visitCount = (user.stats.visitCount || 0) + 1;
  user.stats.totalOrders = (user.stats.totalOrders || 0) + 1;
  user.stats.totalSpend = (user.stats.totalSpend || 0) + (order.totals.grandTotal || 0);
  if (!user.stats.firstOrderAt) user.stats.firstOrderAt = now;
  user.stats.lastOrderAt = now;

  const points = Math.round((order.totals.grandTotal || 0) * user.earnRate());
  user.pointsBalance = (user.pointsBalance || 0) + points;
  return points;
}

export function loyaltySummary(user) {
  const rankLabel = { member: "Thành Viên", gold: "Vàng", platinum: "Bạch Kim" };
  return {
    userId: user._id,
    name: user.name,
    tier: user.tier,
    rankLabel: rankLabel[user.tier] || "Thành Viên",
    earnRate: user.earnRate(),
    pointsBalance: user.pointsBalance || 0,
    stats: {
      timesEatenAtKFC: user.stats?.visitCount || 0,
      totalOrders: user.stats?.totalOrders || 0,
      totalSpend: user.stats?.totalSpend || 0,
      firstOrderAt: user.stats?.firstOrderAt || null,
      lastOrderAt: user.stats?.lastOrderAt || null,
    },
  };
}

export async function getUserOrThrow(userId) {
  const user = await User.findById(userId);
  return user;
}
