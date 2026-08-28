const DATABASE = "zc-web";
const STORE = "preferences";

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(STORE);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function readPreference<T>(
  key: string,
  fallback: T,
): Promise<T> {
  try {
    const database = await openDatabase();
    return await new Promise<T>((resolve, reject) => {
      const request = database.transaction(STORE).objectStore(STORE).get(key);
      request.onsuccess = () =>
        resolve(request.result === undefined ? fallback : (request.result as T));
      request.onerror = () => reject(request.error);
    });
  } catch {
    return fallback;
  }
}

export async function writePreference<T>(
  key: string,
  value: T,
): Promise<void> {
  try {
    const database = await openDatabase();
    await new Promise<void>((resolve, reject) => {
      const transaction = database.transaction(STORE, "readwrite");
      transaction.objectStore(STORE).put(value, key);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
    });
  } catch {
    // Preferences are optional; chat data remains server-side.
  }
}
