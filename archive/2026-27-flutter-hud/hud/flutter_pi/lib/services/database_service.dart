import 'dart:io';
import 'package:path/path.dart';
import 'package:flutter/services.dart';
import 'package:sqflite/sqflite.dart';
import '../models/place.dart';

class DatabaseService {
  static Database? _db;
  static final DatabaseService instance = DatabaseService._internal();
  DatabaseService._internal();

  static const String _assetDbPath = "assets/databases/ottawa.db";
  static const String _localDbName = "ottawa.db";

  Future<Database> get database async {
    if (_db != null) return _db!;
    _db = await _initDatabase();
    return _db!;
  }

  Future<Database> _initDatabase() async {
    final dbDir = await getDatabasesPath();
    final dbPath = join(dbDir, _localDbName);

    // Make sure the directory exists
    await Directory(dbDir).create(recursive: true);

    if (await databaseExists(dbPath)) {
      await deleteDatabase(dbPath);
    }

    try {
      ByteData data = await rootBundle.load(_assetDbPath);
      List<int> bytes = data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes);
      await File(dbPath).writeAsBytes(bytes, flush: true);
    } catch (e) {
      throw Exception('Could not load database from assets: $e');
    }

    return await openDatabase(dbPath, readOnly: true);
  }

  Future<List<Place>> search(String query) async {
    final db = await database;
    query = query.trim();
    if (query.isEmpty) return [];

    final addressMatch = RegExp(r'^(\d+)\s+(.+)').firstMatch(query);
    final isNumberOnly = RegExp(r'^\d+$').hasMatch(query);

    List<Map<String, dynamic>> rows;

    if (addressMatch != null) {
      // "150 Elgin" → house number + street
      final houseNum = addressMatch.group(1)!;
      final streetPart = addressMatch.group(2)!;

      rows = await db.rawQuery('''
        SELECT * FROM places
        WHERE house_number = ?
          AND street LIKE ?
        LIMIT 20
      ''', [houseNum, '%$streetPart%']);

    } else if (isNumberOnly) {
      // "150" → search house numbers only
      rows = await db.rawQuery('''
        SELECT * FROM places
        WHERE house_number = ?
        LIMIT 20
      ''', [query]);

    } else {
      // General — name, street, city, type
      rows = await db.rawQuery('''
        SELECT * FROM places
        WHERE name LIKE ?
          OR street LIKE ?
          OR city LIKE ?
          OR type LIKE ?
        ORDER BY
          CASE
            WHEN name LIKE ? THEN 1
            WHEN name LIKE ? THEN 2
            WHEN street LIKE ? THEN 3
            ELSE 4
          END
        LIMIT 20
      ''', [
        '%$query%',
        '%$query%',
        '%$query%',
        '%$query%',
        '$query%',
        '%$query%',
        '$query%',
      ]);
    }

    return rows.map((row) => Place.fromMap(row)).toList();
  }
}