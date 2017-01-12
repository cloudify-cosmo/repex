def validate(file_path, logger):
    logger.info('Validating %s', file_path)
    logger.info('Validating something very specific...')
    raise RuntimeError('Validation Successful!')
