import Store from "../src/models/Store.js";

const STORES = [
  { code: "HCM-NKKN", name: "KFC Nguyễn Kiệm", district: "Phú Nhuận", city: "TP.HCM", type: "standalone" },
  { code: "HCM-VVM", name: "KFC Vincom Đồng Khởi", district: "Quận 1", city: "TP.HCM", type: "mall" },
  { code: "HCM-AEONTP", name: "KFC AEON Tân Phú", district: "Tân Phú", city: "TP.HCM", type: "mall" },
  { code: "HCM-QT7", name: "KFC Quận 7 SC VivoCity", district: "Quận 7", city: "TP.HCM", type: "mall" },
  { code: "HCM-GV", name: "KFC Gò Vấp Quang Trung", district: "Gò Vấp", city: "TP.HCM", type: "standalone" },
  { code: "HN-VINBW", name: "KFC Vincom Bà Triệu", district: "Hai Bà Trưng", city: "Hà Nội", type: "mall" },
  { code: "HN-CG", name: "KFC Cầu Giấy", district: "Cầu Giấy", city: "Hà Nội", type: "standalone" },
  { code: "HN-AEONHD", name: "KFC AEON Hà Đông", district: "Hà Đông", city: "Hà Nội", type: "mall" },
  { code: "DN-VINHAN", name: "KFC Vincom Đà Nẵng", district: "Hải Châu", city: "Đà Nẵng", type: "mall" },
  { code: "CT-SENSE", name: "KFC Sense City Cần Thơ", district: "Ninh Kiều", city: "Cần Thơ", type: "mall" },
];

export async function seedStores() {
  await Store.deleteMany({});
  const docs = STORES.map((s, i) => ({ ...s, kioskIds: [`${s.code}-K1`, `${s.code}-K2`] }));
  const inserted = await Store.insertMany(docs);
  console.log(`[seed:stores] inserted ${inserted.length} stores`);
  return inserted;
}
