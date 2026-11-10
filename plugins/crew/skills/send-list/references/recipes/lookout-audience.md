# Recipe: the members of a Lookout audience

Turns a Lookout audience, or any warehouse table or query, into `list.csv`: one row per person with an email, a name and the columns the Agent needs. It needs the Lookout MCP (`list_lookout_audiences`, `get_lookout_audience`, `list_warehouses`, `query_warehouse`).

**A Lookout audience cannot sync to Crew by itself.** Lookout pushes a saved audience to RudderStack as an audience source (`rs_source_id`), and RudderStack connects audience sources only to audience and list destinations, such as Braze, HubSpot or Google Ads. Crew takes events on a webhook, and a Webhook destination is not one of them; Lookout's sync menu did not list one either when checked. So this recipe reads the audience's definition and runs the same filter itself.

Ask for these, or use the defaults:

| Input           | Default                                                                                  |
| --------------- | ---------------------------------------------------------------------------------------- |
| Audience        | ask the user; `list_lookout_audiences` shows titles and member counts                    |
| Columns         | `email`, `name`, `id`; ask which facts the Agent needs, such as plan or monthly volume   |
| Order and limit | the user's ranking, or the id column; at most a few hundred rows (see the skill, step 1) |

**Stages and files** (for the funnel): `members.csv` after step 3 (the audience's filter and the limit), then the skill's own stages. The evidence for each person, one entry in `evidence.json`:

- `Lookout`. why: `Member of "<audience title>"`. facts: the columns you selected about them, such as `plan`, `monthly_events`. basis: `<audience id>, <the from table>, the rules as Lookout states them, run <date>`.

## 1. Read the audience

Call `get_lookout_audience`. From the answer use:

- `definition.expression.from`: the table the members come from.
- `definition.expression.idColumn` and `identifier.family`: the member's id. `email` means the id is the email. `opaque` means it is a user id, so take the email from another column of the same table, and keep the id: it is the person's `id` in your product, which joins the list to what Crew already knows.
- `definition.expression.where`: the filter, as a tree (step 2).
- `rules`: the filter in words. Show them to the user, and use them to check your SQL.
- `count.members` and `count.counted_at`: the size Lookout counted, to check your count against.

## 2. Turn the filter into SQL

The tree has three kinds of node:

- `{"and": [...]}` or `{"or": [...]}`: join the children with `AND` or `OR`, in parentheses.
- `{"attribute": {"path", "operator", "value"}}`: one condition on a column of the `from` table. Seen so far: `eq` (`=`), `nnull` (`IS NOT NULL`), `nlike` (`NOT LIKE`). Write any other operator the way its name and the matching sentence in `rules` say, and check the count in step 3.
- `{"rawSql": {"sql"}}`: SQL to paste as it is. It refers to the `from` table as `u` (for example `r.USERID = u.ID`), so always write `FROM <from> u`.

The audience's `warehouse_id` is not an id `query_warehouse` accepts. Call `list_warehouses` and use the warehouse that has the `from` table.

To find column names, do not call `describe_table` on a wide table: on a users table of 590 columns its answer was too large to read. Query the information schema for the names you need instead:

```sql
SELECT column_name, data_type
FROM INFORMATION_SCHEMA.COLUMNS
WHERE table_schema = '<schema>' AND table_name = '<table>'
  AND column_name ILIKE ANY ('%EMAIL%', '%NAME%', '%TITLE%', '%COMPANY%', '%PLAN%')
LIMIT 100
```

## 3. Count, then fetch

Count first, with the whole filter:

```sql
SELECT COUNT(*) AS members FROM <from> u WHERE <filter> LIMIT 1
```

The count should be close to `count.members`. It drifts as the data changes: in one check, a large audience Lookout had counted a week earlier was off by under 1%, and a small one counted five weeks earlier by about 8%. A gap far bigger than the time since `counted_at` explains means the SQL is wrong; fix it before you go on. Tell the user both numbers.

If the count is more than a few hundred, ask the user how to narrow it (a ranking and a top N, or a segment), or move to a scheduled Reverse ETL sync (the `connect-warehouse` skill), with this recipe's query as its model. Then fetch. `query_warehouse` refuses a query without a literal `LIMIT`:

```sql
SELECT u.EMAIL AS email,
       COALESCE(u.NAME, TRIM(CONCAT(COALESCE(u.FIRST_NAME, ''), ' ', COALESCE(u.LAST_NAME, '')))) AS name,
       TO_VARCHAR(u.ID) AS id,
       <the columns the Agent needs, each with a lowercase alias>
FROM <from> u
WHERE <filter> AND u.EMAIL IS NOT NULL
ORDER BY <the ranking, else u.ID>
LIMIT <N>
```

- Alias every column for what it means: the aliases become the column names in `list.csv`, and the Agent reads them as event properties. Snowflake returns them in upper case (`EMAIL`, `PLAN`); `send_leads.py` lowercases every header, so either works.
- `TO_VARCHAR` the id. A number is not a user id Crew accepts.
- Do not select a timestamp the Agent does not need. If it needs one, select it formatted as a date.
- Select only what the Agent should know. Every column reaches the model, and can end up in the message.

Write the rows to `members.csv`, then to `list.csv`, and go back to step 2 of the skill. Free-mail and personal addresses stay in the list unless the user asks to drop them: for a product's own users they are often the only address.
