import csv


class StreamsInput(str):
    """Streams handed to Pinch in memory, in place of a streams file.

    Pinch and HeatPumpIntegration take a file name and only cut a label from
    it (name[:-4]); Streams below reads the rows. So this is a name that
    carries its rows: the request's data never becomes a file on the server.
    """
    rows: list


def streams_input(t_min, streams):
    """The rows of a streams file (Tmin, header, one row per stream), in memory.

    `streams` yields (CP, T_supply, T_target). The values are written as text,
    exactly as the file held them, so Streams parses the same numbers.
    """
    data = StreamsInput("streams.csv")
    data.rows = [["Tmin", str(t_min)], ["CP", "TSUPPLY", "TTARGET"]]
    data.rows += [[str(cp), str(ts), str(tt)] for cp, ts, tt in streams]
    return data


class Streams:

    def __init__(self, streams_data_file):

        self.tmin =              0
        self.numberOf =          0
        self.streamsData =       []

        self._rawStreamsData =   []
        self._index =            0
        self._length =           0




        if isinstance(streams_data_file, StreamsInput):
            self._rawStreamsData = [list(row) for row in streams_data_file.rows]
        else:
            with open(streams_data_file, newline='') as f:
                reader = csv.reader(f)
                for row in reader:
                    self._rawStreamsData.append(row)

        if (self._rawStreamsData[0][0].strip() != 'Tmin' or
                [ item.strip() for item in self._rawStreamsData[1] ] != ['CP', 'TSUPPLY', 'TTARGET']):
            raise Exception("""\n[ERROR] Bad formatting in streams data file. \n
                    The first two rows of the streams data file should be: \n
                    `` Tmin, <TMIN VALUE> ''
                    `` CP, TSUPPLY, TTARGET ''\n
                    Where CP is the heat capacity (kW / degC);
                    TSUPPLY is the starting temperature of the given stream (degC);
                    TTARGET is the ending temperature of the given stream (degC);\n""")

        self.create_streams()


    def create_streams(self):
        try:
            self.tmin = float(self._rawStreamsData[0][1])
        except ValueError:
            print("\n[ERROR] Wrong type supplied for Tmin in the streams data file. Perhaps used characters?\n")
            raise
        except IndexError:
            print("\n[ERROR] Missing value for Tmin in the streams data file.\n")
            raise
        except:
            print("\n[ERROR] Unexpected error for Tmin. Try using the supplied streams data file format.\n")
            raise


        for rawStream in self._rawStreamsData[2:]:
            try:
                stream = {}

                if float(rawStream[1]) > float(rawStream[2]):
                    stream["type"] = "HOT"
                else:
                    stream["type"] = "COLD"

                stream["cp"] = float(rawStream[0])
                stream["ts"] = float(rawStream[1])
                stream["tt"] = float(rawStream[2])

                self.streamsData.append(stream)

            except ValueError:
                print("\n[ERROR] Wrong number type supplied in the streams data file. Perhaps used characters?\n")
                raise
            except IndexError:
                print("\n[ERROR] Missing number in the streams data file.\n")
                raise
            except:
                print("\n[ERROR] Unexpected error. Try using the supplied streams data file format.\n")
                raise

        self._length = len(self.streamsData)
        self.numberOf = len(self.streamsData)
        if (self._length < 2):
            raise Exception("\n[ERROR] Need to supply at least 2 streams in the streams data file.\n")


    def __iter__(self):
        return self


    def __next__(self):
        if self._index == self._length:
            self._index = 0
            raise StopIteration
        self._index = self._index + 1

        return self.streamsData[self._index - 1]


    def print_tmin(self):
        print(self.tmin)


    def print_streams(self):
        for stream in self.streamsData:
            print(stream)


    def print_raw_streams(self):
        for rawStream in self._rawStreamsData:
            print(rawStream)