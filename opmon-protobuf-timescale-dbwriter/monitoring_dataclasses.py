"""
Simple data classes for monitoring metrics
"""

from dataclasses import dataclass

@dataclass
class QueueMetrics:
    '''Metrics for monitoring the state of the entry and writer queues.'''
    entry_queue_size: int = 0
    writer_queue_size: int = 0
    entries_created: int = 0
    entries_dequeued: int = 0
    batches_processed: int = 0
    entries_rejected: int = 0
