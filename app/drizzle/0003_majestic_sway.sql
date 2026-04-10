CREATE TABLE `search_history` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`name` text NOT NULL,
	`lon` real NOT NULL,
	`lat` real NOT NULL,
	`used_at` text DEFAULT (datetime('now')) NOT NULL
);
