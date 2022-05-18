#!/usr/bin/python3
import av
import av.datasets

if True:
        with av.open(av.datasets.curated('/dev/dvd')) as src:
            with av.open("/tmp/tmp.ts", "w") as dst:  # FIXME path
                src.streams.video[0].thread_type = 'AUTO'  # "go faster" stripes
                # Begin remuxing.
                src_stream = src.streams.video[0]
                dst_stream = dst.add_stream(template=src_stream)
                for i, packet in enumerate(src.demux(src_stream)):
                #    progressfunc(i / 1000)  # tell GTK popup (FIXME: get actual frame count)
                    # Skip "flushing" packets demux generates.
                    if packet.dts is None:
                        continue
                    # We need to assign the packet to the new stream.
                    packet.stream = dst_stream
                    dst.mux(packet)
print('All done!')
