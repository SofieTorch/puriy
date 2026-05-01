/**
 * Web-specific DatabaseProvider.
 *
 * Bypasses drizzle-orm's built-in migrator which uses `SERIAL PRIMARY KEY`
 * (PostgreSQL syntax) for its internal __drizzle_migrations table — wa-sqlite
 * on web rejects this. Instead, we run migration SQL directly via expo-sqlite's
 * execAsync, then create the drizzle instance normally.
 */
'use client';

import { drizzle } from 'drizzle-orm/expo-sqlite';
import { SQLiteProvider, useSQLiteContext } from 'expo-sqlite';
import type { SQLiteDatabase } from 'expo-sqlite';
import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import NetInfo from '@react-native-community/netinfo';

import * as schema from '@/db/schema';
import migrations from '@/drizzle/migrations';
import { setDb } from '@/lib/db-ref';
import { syncPendingRecordings } from '@/services/sync';

function SyncOnReconnect({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener((state) => {
      if (state.isConnected) {
        syncPendingRecordings();
      }
    });
    return () => unsubscribe();
  }, []);

  return <>{children}</>;
}

/**
 * Run migrations manually without drizzle's migrator.
 * Creates a tracking table with valid SQLite syntax and runs each migration
 * that hasn't been applied yet.
 */
async function runMigrations(expoDb: SQLiteDatabase): Promise<void> {
  // Create tracking table with valid SQLite syntax (not SERIAL)
  await expoDb.execAsync(`
    CREATE TABLE IF NOT EXISTS "__drizzle_migrations" (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      hash text NOT NULL,
      created_at numeric
    )
  `);

  // Check which migrations have been applied
  const applied = await expoDb.getAllAsync<{ created_at: number }>(
    'SELECT created_at FROM "__drizzle_migrations" ORDER BY created_at DESC LIMIT 1'
  );
  const lastApplied = applied[0]?.created_at ?? 0;

  // Run pending migrations
  for (const entry of migrations.journal.entries) {
    if (entry.when <= lastApplied) continue;

    const key = `m${entry.idx.toString().padStart(4, '0')}` as keyof typeof migrations.migrations;
    const sql = migrations.migrations[key];
    if (!sql) throw new Error(`Missing migration: ${entry.tag}`);

    const statements = sql.split('--> statement-breakpoint');

    await expoDb.execAsync('BEGIN');
    try {
      for (const stmt of statements) {
        const trimmed = stmt.trim();
        if (trimmed) await expoDb.execAsync(trimmed);
      }
      await expoDb.runAsync(
        'INSERT INTO "__drizzle_migrations" ("hash", "created_at") VALUES (?, ?)',
        ['', entry.when]
      );
      await expoDb.execAsync('COMMIT');
    } catch (e) {
      await expoDb.execAsync('ROLLBACK');
      throw e;
    }
  }
}

function MigrationsGate({ children }: { children: React.ReactNode }) {
  const expoDb = useSQLiteContext();
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Run migrations and create drizzle instance
  const db = useMemo(() => {
    const d = drizzle(expoDb, { schema });
    setDb(d);
    return d;
  }, [expoDb]);

  useEffect(() => {
    runMigrations(expoDb)
      .then(() => setReady(true))
      .catch((e) => setError(e instanceof Error ? e : new Error(String(e))));
  }, [expoDb]);

  if (error) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', padding: 20 }}>
        <Text style={{ color: 'red', marginBottom: 10 }}>Migration error</Text>
        <Text style={{ color: '#666' }}>{error.message}</Text>
      </View>
    );
  }

  if (!ready) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
        <ActivityIndicator size="large" />
        <Text style={{ marginTop: 12, color: '#666' }}>Initializing database...</Text>
      </View>
    );
  }

  return <SyncOnReconnect>{children}</SyncOnReconnect>;
}

export function DatabaseProvider({ children }: { children: React.ReactNode }) {
  return (
    <SQLiteProvider databaseName="cbba-mobility.db">
      <MigrationsGate>{children}</MigrationsGate>
    </SQLiteProvider>
  );
}
