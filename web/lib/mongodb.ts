import { MongoClient, Db } from "mongodb"

// =================================================================
// MongoDB Connection Utility
// Connects to MongoDB Atlas using MONGODB_URI environment variable
// Uses a cached connection to avoid creating new connections on every request
// =================================================================

const options = {}

let client: MongoClient | null = null
let clientPromise: Promise<MongoClient> | null = null

function getUri(): string | null {
  const uri = process.env.MONGODB_URI
  if (!uri) return null
  // Validate that URI starts with mongodb:// or mongodb+srv://
  if (!uri.startsWith("mongodb://") && !uri.startsWith("mongodb+srv://")) {
    console.warn("[v0] Invalid MONGODB_URI format - must start with mongodb:// or mongodb+srv://")
    return null
  }
  return uri
}

function initializeClient(): Promise<MongoClient> | null {
  const uri = getUri()
  if (!uri) return null

  if (process.env.NODE_ENV === "development") {
    // In development, use a global variable to preserve the client across HMR
    const globalWithMongo = global as typeof globalThis & {
      _mongoClientPromise?: Promise<MongoClient>
    }

    if (!globalWithMongo._mongoClientPromise) {
      client = new MongoClient(uri, options)
      globalWithMongo._mongoClientPromise = client.connect()
    }
    return globalWithMongo._mongoClientPromise
  } else {
    // In production, create a new client
    client = new MongoClient(uri, options)
    return client.connect()
  }
}

export async function getDb(): Promise<Db | null> {
  const uri = getUri()
  if (!uri) {
    console.log("[v0] MongoDB URI not configured or invalid, returning null")
    return null
  }

  // Lazy initialization
  if (!clientPromise) {
    clientPromise = initializeClient()
  }
  
  if (!clientPromise) {
    return null
  }
  
  try {
    const mongoClient = await clientPromise
    // Extract database name from URI or use default
    const dbName = new URL(uri).pathname.slice(1) || "dam-base"
    return mongoClient.db(dbName)
  } catch (error) {
    console.error("[v0] MongoDB connection error:", error)
    return null
  }
}

export function isMongoConfigured(): boolean {
  return !!getUri()
}

export default clientPromise
