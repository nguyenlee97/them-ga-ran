import Voucher from "../src/models/Voucher.js";

const VOUCHERS = [
  { code: "WELCOME25", description: "Ưu đãi thành viên mới - giảm 25K", type: "amount", value: 25000, conditions: { minOrder: 89000 } },
  { code: "COMBO10", description: "Giảm 10% cho đơn combo", type: "percent", value: 10, conditions: { minOrder: 150000 } },
  { code: "FREESHIP0", description: "Giảm 15K", type: "amount", value: 15000, conditions: { minOrder: 60000 } },
];

export async function seedVouchers() {
  await Voucher.deleteMany({});
  const now = new Date();
  const docs = VOUCHERS.map((v) => ({
    ...v, active: true, validFrom: now, validTo: new Date(now.getTime() + 365 * 864e5),
  }));
  const inserted = await Voucher.insertMany(docs);
  console.log(`[seed:vouchers] inserted ${inserted.length} vouchers`);
  return inserted;
}
