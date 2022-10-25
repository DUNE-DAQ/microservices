crontab -l > cron_jobs
#echo new cron into cron file
echo "0 5 * * * /get_ticket_np04daq.sh" >> cron_jobs
#install new cron file
crontab cron_jobs

exec gunicorn -b 0.0.0.0:5005 --workers=1 --worker-class=gevent --timeout 5000000000 --log-level=debug logbook:app
