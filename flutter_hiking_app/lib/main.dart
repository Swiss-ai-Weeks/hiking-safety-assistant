import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:path_provider/path_provider.dart';
import 'package:sqlite3/sqlite3.dart';

void main() => runApp(const HikingSafetyApp());

class HikingSafetyApp extends StatelessWidget {
  const HikingSafetyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Hiking Safety Assistant',
      theme: ThemeData(
        primarySwatch: Colors.green,
        useMaterial3: true,
      ),
      home const HomeScreen(),
    );
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  String _result = '';
  Future<void> _loadSwissData() async {
    try {
      final dir = await getApplicationDocumentsDirectory();
      final dbPath = '${dir.path}/swiss_hiking.db';
      final db = sqlite3.open(dbPath);
      db.execute('''CREATE TABLE IF NOT EXISTS routes (
        id INTEGER PRIMARY KEY,
        name TEXT,
        difficulty TEXT,
        length_km REAL
      )''');
      db.execute('''CREATE TABLE IF NOT EXISTS weather (
        id INTEGER PRIMARY KEY,
        route_id INTEGER,
        temperature REAL,
        precipitation REAL,
        forecast TEXT,
        FOREIGN KEY(route_id) REFERENCES routes(id)
      )''');
      // Sample Swiss route data
      db.execute(
          "INSERT OR IGNORE INTO routes VALUES (1, 'Hardergrat', 'hard', 5.2)");
      db.execute(
          "INSERT OR IGNORE INTO routes VALUES (2, 'Eiger Trail', 'moderate', 9.7)");
      db.execute(
          "INSERT OR IGNORE INTO weather VALUES (1, 1, 8.5, 0.0, 'Clear')");
      db.execute(
          "INSERT OR IGNORE INTO weather VALUES (2, 2, 12.0, 0.0, 'Partly cloudy')");
      db.close();
      setState(() => _result = 'Swiss hiking data initialized at $dbPath');
    } catch (e) {
      setState(() => _result = 'Error: $e');
    }
  }

  Future<void> _getRouteConditions(String routeName) async {
    setState(() => _result = 'Loading conditions for: $routeName');
    // In a full implementation, this would query Swiss Open Data APIs
    await Future.delayed(const Duration(seconds: 1));
    setState(() =>
        _result = 'Conditions for $routeName: checking weather and terrain data...');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Hiking Safety Assistant')),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text('Swiss Hiking Safety Assistant'),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: _loadSwissData,
              child: const Text('Load Swiss Hiking Data'),
            ),
            const SizedBox(height: 10),
            ElevatedButton(
              onPressed: () => _getRouteConditions('Hardergrat'),
              child: const Text('Check Route Conditions'),
            ),
            const SizedBox(height: 20),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(16.0),
                child: Text(_result.isEmpty
                    ? 'Tap a button to get started'
                    : _result),
              ),
            ),
          ],
        ),
      ),
    );
  }
}