import mongoose from "mongoose";

/**
 * Single shared Mongo connection. Call connectDB() once at boot.
 */
export async function connectDB(uri = process.env.MONGODB_URI) {
  if (!uri) throw new Error("MONGODB_URI is not set");
  mongoose.set("strictQuery", true);
  await mongoose.connect(uri, { serverSelectionTimeoutMS: 8000 });
  console.log(`[db] connected → ${uri.replace(/\/\/.*@/, "//***@")}`);
  return mongoose.connection;
}

export default mongoose;
