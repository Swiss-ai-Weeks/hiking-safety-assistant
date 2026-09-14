import 'package:sqlite3/sqlite3.dart';

class SQLiteHelper {
  static Database? _db;

  static Database get db {
    if (_db != null) return _db!;
    final path = '/sandbox/hiking-safety-assistant/hiking.db';
    _db = sqlite3.open(path);
    _db!.execute('''CREATE TABLE IF NOT EXISTS routes (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      difficulty TEXT,
      length_km REAL
    )''');
    _db!.execute('''CREATE TABLE IF NOT EXISTS weather (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      route_id TEXT,
      temperature REAL,
      precipitation REAL,
      condition TEXT,
      forecast TEXT,
      FOREIGN KEY(route_id) REFERENCES routes(id)
    )''');
    return _db!;
  }

  static void close() => _db?.close();
}