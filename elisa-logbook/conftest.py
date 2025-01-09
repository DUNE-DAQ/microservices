
def pytest_addoption(parser):
    parser.addoption(
        '--system',
        action="store",
        type=str,
        nargs='+',
        default=['npvd', 'pdsp', 'pddp'],
        help="Name of the system(s) to test"
    )