These scripts expect that you've got `DATABASE_URI` defined in your environment.

You can make partitions with something like:

```shell
partitions_for_all_tables.sh | psql "${DATABASE_URI}"
```
