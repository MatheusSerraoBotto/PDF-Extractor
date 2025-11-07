"""
Batch processing orchestration with parallel execution.

Handles batch extraction requests by processing multiple PDFs concurrently
with configurable concurrency limits and streaming results.
"""

import asyncio
import logging
from typing import List

from src.config.settings import get_settings
from src.core.pipeline import run_extraction
from src.models.schema import (
    BatchExtractionItem,
    BatchItemResult,
    BatchSummary,
    ExtractionRequest,
)

logger = logging.getLogger(__name__)


async def process_batch_parallel(
    items: List[BatchExtractionItem],
    use_cache: bool = True,
):
    """
    Process a batch of extraction items in parallel and yield results as they complete.

    Args:
        items: List of extraction items to process
        use_cache: Whether to use Redis cache for results

    Yields:
        BatchItemResult for each completed item, then BatchSummary at the end

    Design:
        - Processes items in parallel using asyncio.as_completed
        - Each item runs independently in a threadpool to avoid blocking
        - Results yielded immediately as they complete (true streaming)
        - Errors in individual items don't stop other items from processing
        - Respects max_concurrent_extractions to avoid overwhelming OpenAI API
    """
    settings = get_settings()

    async def process_one(index: int, item: BatchExtractionItem) -> BatchItemResult:
        """Process a single extraction item and return result."""
        try:
            logger.info(
                f"Starting extraction for item {index}: {item.label} - {item.pdf_path}"
            )

            # Convert BatchExtractionItem to ExtractionRequest
            request = ExtractionRequest(
                label=item.label,
                extraction_schema=item.extraction_schema,
                pdf_path=item.pdf_path,
            )

            # Run extraction in threadpool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, run_extraction, request, use_cache
            )

            # Create success result
            batch_result = BatchItemResult(
                index=index,
                status="completed",
                label=item.label,
                fields=result.fields,
                meta=result.meta,
            )
            logger.info(f"Successfully processed item {index}: {item.label}")
            return batch_result

        except Exception as e:
            # Create error result
            error_msg = f"{type(e).__name__}: {str(e)}"
            batch_result = BatchItemResult(
                index=index,
                status="error",
                label=item.label,
                error=error_msg,
            )
            logger.error(f"Failed to process item {index}: {item.label} - {error_msg}")
            return batch_result

    # Create semaphore to limit concurrency
    semaphore = asyncio.Semaphore(settings.max_concurrent_extractions)

    async def process_with_semaphore(index: int, item: BatchExtractionItem) -> BatchItemResult:
        """Wrapper to enforce concurrency limit."""
        async with semaphore:
            return await process_one(index, item)

    # Process all items in parallel and yield results as they complete
    logger.info(f"Starting batch processing of {len(items)} items")

    tasks = [process_with_semaphore(i, item) for i, item in enumerate(items)]
    completed_count = 0
    successful_count = 0
    failed_count = 0

    # Use as_completed to yield results as soon as they're ready
    for coro in asyncio.as_completed(tasks):
        result = await coro
        completed_count += 1

        if result.status == "completed":
            successful_count += 1
        else:
            failed_count += 1

        logger.info(f"Yielding result {completed_count}/{len(items)}: index={result.index}, status={result.status}")
        logger.info(f"Result details: {result}")
        yield result
        await asyncio.sleep(0.250)

    # await asyncio.sleep(5)  # Allow event loop to process any remaining tasks

    # After all items processed, yield summary
    summary = BatchSummary(
        status="done",
        total=len(items),
        successful=successful_count,
        failed=failed_count,
    )

    logger.info(
        f"Batch processing complete: {successful_count}/{len(items)} successful, {failed_count} failed"
    )

    yield summary
